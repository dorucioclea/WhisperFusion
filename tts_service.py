import functools
import time
import logging
logging.basicConfig(level = logging.INFO)

from websockets.sync.server import serve
from whisperspeech.pipeline import Pipeline

class WhisperSpeechTTS:
    def __init__(self):
        pass
    
    def initialize_model(self):
        self.pipe = Pipeline(s2a_ref='collabora/whisperspeech:s2a-q4-tiny-en+pl.model')
        self.last_llm_response = None

    def run(self, host, port, audio_queue=None):
        # initialize and warmup model
        self.initialize_model()
        for i in range(3): self.pipe.vocoder.decode(self.pipe.generate_atoks("Hello, I am warming up."))

        with serve(
            functools.partial(self.start_whisperspeech_tts, audio_queue=audio_queue), 
            host, port
            ) as server:
            server.serve_forever()

    def start_whisperspeech_tts(self, websocket, audio_queue=None):
        self.eos = False
        self.output_audio = None

        while True:
            if audio_queue.empty(): continue
            
            # check if this websocket exists
            try:
                websocket.ping()
            except Exception as e:
                del websocket
                break

            llm_response = audio_queue.get()
            llm_output = llm_response["llm_output"][0]
            self.eos = llm_response["eos"]

            # only process if the output updated
            if self.last_llm_response != llm_output.strip():
                logging.INFO("[WhisperSpeech INFO:] Tunning TTS inference ...")
                audio = self.pipe.vocoder.decode(self.pipe.generate_atoks(llm_output.strip()))
                self.output_audio = audio.cpu().numpy()
                self.last_llm_response = llm_output.strip()

            if self.eos and self.output_audio is not None:
                try:
                    websocket.send(self.output_audio.tobytes())
                except Exception as e:
                    logging.error("[WhisperSpeech INFO:] Audio error:", e)

