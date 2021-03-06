#
# Copyright 2018 Picovoice Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import os
import platform
import struct
import sys
from datetime import datetime
from threading import Thread

import numpy as np
import pyaudio
import soundfile

sys.path.append(os.path.join(os.path.dirname(__file__), '../../binding/python'))

from porcupine import Porcupine


class PorcupineDemo(Thread):
    """
    Demo class for wake word detection (aka Porcupine) library. It creates an input audio stream from a microphone,
    monitors it, and upon detecting the specified wake word prints the detection time on console. It optionally saves
    the recorded audio into a file for further review.
    """

    def __init__(
            self,
            library_path,
            model_file_path,
            keyword_file_path,
            sensitivity=0.5,
            input_device_index=None,
            output_path=None):

        """
        Constructor.

        :param library_path: Absolute path to Porcupine's dynamic library.
        :param model_file_path: Absolute path to the model parameter file.
        :param keyword_file_path: Absolute path to keyword file.
        :param sensitivity: Sensitivity parameter. For more information refer to 'include/pv_porcupine.h'
        :param input_device_index: Optional argument. If provided, audio is recorded from this input device. Otherwise,
        the default audio input device is used.
        :param output_path: If provided recorded audio will be stored in this location at the end of the run.
        """

        super(PorcupineDemo, self).__init__()

        self._library_path = library_path
        self._model_file_path = model_file_path
        self._keyword_file_path = keyword_file_path
        self._sensitivity = float(sensitivity)
        self._input_device_index = input_device_index

        self._output_path = output_path
        if self._output_path is not None:
            self._recorded_frames = []

    def run(self):
        """
         Creates an input audio stream, initializes wake word detection (Porcupine) object, and monitors the audio
         stream for occurrences of the wake word. It prints the time of detection for each occurrence.
         """

        porcupine = None
        pa = None
        audio_stream = None
        try:
            porcupine = Porcupine(
                library_path=self._library_path,
                model_file_path=self._model_file_path,
                keyword_file_path=self._keyword_file_path,
                sensitivity=self._sensitivity)

            pa = pyaudio.PyAudio()
            audio_stream = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length,
                input_device_index=self._input_device_index)

            while True:
                pcm = audio_stream.read(porcupine.frame_length)
                pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

                if self._output_path is not None:
                    self._recorded_frames.append(pcm)

                result = porcupine.process(pcm)
                if result:
                    print('[%s] detected keyword' % str(datetime.now()))
        except KeyboardInterrupt:
            print('stopping ...')
        finally:
            if porcupine is not None:
                porcupine.delete()

            if audio_stream is not None:
                audio_stream.close()

            if pa is not None:
                pa.terminate()

            if self._output_path is not None and len(self._recorded_frames) > 0:
                recorded_audio = np.concatenate(self._recorded_frames, axis=0).astype(np.int16)
                soundfile.write(self._output_path, recorded_audio, samplerate=porcupine.sample_rate, subtype='PCM_16')

    _AUDIO_DEVICE_INFO_KEYS = ['index', 'name', 'defaultSampleRate', 'maxInputChannels']

    @classmethod
    def show_audio_devices_info(cls):
        """ Provides information regarding different audio devices available. """

        pa = pyaudio.PyAudio()

        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            print(', '.join("'%s': '%s'" % (k, str(info[k])) for k in cls._AUDIO_DEVICE_INFO_KEYS))

        pa.terminate()


def _system():
    x = platform.system()
    if x == 'Linux':
        return 'linux'
    elif x == 'Darwin':
        return 'mac'
    else:
        raise NotImplementedError('Porcupine is not supported on %s yet!' % x)


def _machine():
    x = platform.machine()
    if x == 'x86_64' or x == 'i386':
        return x
    else:
        raise NotImplementedError('Porcupine is not supported on %s yet!' % x)


def _dynamic_library_extension():
    x = _system()
    if x == 'linux':
        return 'so'
    elif x == 'mac':
        return 'dylib'
    else:
        raise NotImplementedError('Porcupine is not supported on %s yet!' % x)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--keyword_file_path', help='absolute path to keyword file', type=str)

    default_library_path = os.path.join(
            os.path.dirname(__file__),
            '../../lib/%s/%s/libpv_porcupine.%s' % (_system(), _machine(), _dynamic_library_extension()))
    parser.add_argument(
        '--library_path',
        help="absolute path to Porcupine's dynamic library",
        type=str,
        default=default_library_path)

    parser.add_argument(
        '--model_file_path',
        help='absolute path to model parameter file',
        type=str,
        default=os.path.join(os.path.dirname(__file__), '../../lib/common/porcupine_params.pv'))

    parser.add_argument('--sensitivity', help='detection sensitivity [0, 1]', default=0.5)
    parser.add_argument('--input_audio_device_index', help='index of input audio device', type=int, default=None)

    parser.add_argument(
        '--output_path',
        help='absolute path to where recorded audio will be stored. If not set, it will be bypassed.',
        type=str,
        default=None)

    parser.add_argument('--show_audio_devices_info', action='store_true')

    args = parser.parse_args()

    if args.show_audio_devices_info:
        PorcupineDemo.show_audio_devices_info()
    else:
        if not args.keyword_file_path:
            raise ValueError('keyword file path is missing')

        PorcupineDemo(
            library_path=args.library_path,
            model_file_path=args.model_file_path,
            keyword_file_path=args.keyword_file_path,
            sensitivity=args.sensitivity,
            output_path=args.output_path,
            input_device_index=args.input_audio_device_index).run()
