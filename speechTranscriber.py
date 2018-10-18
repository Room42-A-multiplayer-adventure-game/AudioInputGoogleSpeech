#!/usr/bin/env python

# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Google Cloud Speech API sample application using the REST API for batch
processing.
Example usage:
    python transcribe.py resources/audio.raw
    python transcribe.py gs://cloud-samples-tests/speech/brooklyn.flac
"""

# sound recording script from https://gist.github.com/mabdrabo/8678538

# osc from https://pypi.org/project/python-osc/

# [START import_libraries]
import argparse
import io
import pyaudio
import wave
import time
from queue import Queue
import threading
from pythonosc import osc_message_builder
from pythonosc import udp_client
from pythonosc import dispatcher
from pythonosc import osc_server
import argparse
from pathlib import Path
import os
# [END import_libraries]

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = int(RATE / 10)
RECORD_SECONDS = 14
IP = "127.0.0.1"
CLIENT_PORT = 11111
SERVER_PORT = 22222

class SpeechTranscriber(object): 

    #Send a message as OSC message to the OSC receiver
    def sendOsc(self, message):
        mapping = {ord(u"ä"): u"ae", ord(u"ö"): u"oe", ord(u"ü"): u"ue", ord(u"Ä"): u"Ae", ord(u"Ö"): u"Oe", ord(u"Ü"): u"Ue", ord(u"ß"): u"ss"}
        translatedMessage = message.translate(mapping)

        parser = argparse.ArgumentParser()
        parser.add_argument("--ip", default=IP, help="The ip of the OSC server")
        parser.add_argument("--port", type=int, default=CLIENT_PORT, help="The port the OSC server is listening on")
        args = parser.parse_args()

        client = udp_client.SimpleUDPClient(args.ip, args.port)
        client.send_message("/filter", translatedMessage)

    # [START def_transcribe_file]
    def transcribe_file(self, speech_file):
        """Transcribe the given audio file."""
        from google.cloud import speech
        from google.cloud.speech import enums
        from google.cloud.speech import types
        client = speech.SpeechClient()

        # [START migration_sync_request]
        # [START migration_audio_config_file]
        with io.open(speech_file, 'rb') as audio_file:
            content = audio_file.read()

        audio = types.RecognitionAudio(content=content)
        config = types.RecognitionConfig(
            encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
            language_code='de-DE')
        # [END migration_audio_config_file]

        # [START migration_sync_response]
        response = client.recognize(config, audio)
        # [END migration_sync_request]
        # Each result is for a consecutive portion of the audio. Iterate through
        # them to get the transcripts for the entire audio file.
        for result in response.results:
            # The first alternative is the most likely one for this portion.
            print(u'{}'.format(result.alternatives[0].transcript))
            # send transcript as osc message to processing and output program
            self.sendOsc(str(result.alternatives[0].transcript))
        # [END migration_sync_response]
    # [END def_transcribe_file]

    def recordAudioChunk(self, now):    
        audio = pyaudio.PyAudio()
        
        stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK)
        frames = []
        
        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            frames.append(data)
        
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        filename = "audio/" + str(now) + ".wav"
        waveFile = wave.open(filename, 'wb')
        waveFile.setnchannels(CHANNELS)
        waveFile.setsampwidth(audio.get_sample_size(FORMAT))
        waveFile.setframerate(RATE)
        waveFile.writeframes(b''.join(frames))
        waveFile.close()
        self.__chunks.put(filename)

    def recordAudio(self):
        while self.__recorderIsRunning:
            now = time.time()
            self.recordAudioChunk(now)
            time.sleep(0.1)
            
    def transcribe(self):
        while self.__transcriberIsRunning:
            chunk = self.__chunks.get()
            self.transcribe_file(chunk)
            os.remove(chunk)

    def startRecording(self): 
        print("start recording...")
        self.__recorderIsRunning = True
        self.__transcriberIsRunning = True
        self.__recording = self.setupRecordingProcess()
        self.__transcribing = self.setupTranscribingProcess()
        self.__recording.start()
        self.__transcribing.start()

    def pauseRecording(self):
        print("pause recording...")
        if (self.__recorderIsRunning):
             self.__recorderIsRunning = False
             self.__recording.join()
        if (self.__transcriberIsRunning):
            self.__transcriberIsRunning = False
            self.__transcribing.join()

    def shutDown(self):
        print("shut down program...")
        self.pauseRecording()
        self.__server.shutdown()
        self.__listeningToOsc.join()

    def handleOscInput(self, unused_addr, args):
        message = ""
        for s in args:
            message += s
        print("message: " + message)

        if(message == "start"):
            self.startRecording()
        if(message == "pause"):
            self.pauseRecording()
        if(message == "shutdown"):
            self.shutDown()

    def startOscServer(self):
        # listen for osc input    
        print("Serving on {}".format(self.__server.server_address))
        self.__server.serve_forever()
    
    def setupOscServer(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--ip", default=IP, help="The ip to listen on")
        parser.add_argument("--port", type=int, default=SERVER_PORT, help="The port to listen on")
        args = parser.parse_args()
        disp = dispatcher.Dispatcher()
        disp.map("/audioStatus", self.handleOscInput)
        server = osc_server.ThreadingOSCUDPServer(
            (args.ip, args.port), disp)
        return server

    def setupRecordingProcess(self):
        recording = threading.Thread(name="recording", target=self.recordAudio)
        return recording
    
    def setupTranscribingProcess(self):
        transcribing = threading.Thread(name="transcribing", target=self.transcribe)
        return transcribing

    def __init__(self): 
        self.__chunks = Queue()
        self.__server = self.setupOscServer()
        self.__recording = self.setupRecordingProcess()
        self.__transcribing = self.setupTranscribingProcess()

        # listen for OSC message
        self.__listeningToOsc = threading.Thread(name="listeningToOsc", target=self.startOscServer)
        self.__listeningToOsc.start()

        self.__recorderIsRunning = False
        self.__transcriberIsRunning = False