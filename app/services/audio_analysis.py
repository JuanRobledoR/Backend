import requests
import librosa
import numpy as np
import tempfile
import os
import io
from app.services.spotify_service import SpotifyService
import soundfile as sf

DEEZER_API_URL = "https://api.deezer.com"

class AudioAnalysisService:
    def __init__(self):
        pass

    def _convertir_cancion(self, cancion_URL):
        try:
            #cancion_URL = "https://cdnt-preview.dzcdn.net/api/1/1/f/5/c/0/f5c28e896b108f7fab26c2f694274d38.mp3?hdnea=exp=1763416411~acl=/api/1/1/f/5/c/0/f5c28e896b108f7fab26c2f694274d38.mp3*~data=user_id=0,application_id=42~hmac=1772b2a155f853c879c136abd73fccf0870454ec960f53459eed2746fbb87fdb"
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(cancion_URL, headers=headers)
            r.raise_for_status()

            #archivo temporal fisicow
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(r.content)
                temp_path = temp_file.name

            try:

                #y es la onda de audio
            #sr es el sample rate (velocidad de muestreo, p/d 22050hz)
                y, sr = librosa.load(temp_path, duration=30)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            return y, sr
        
        except Exception as e:
            print(e)
            return None, None

            



    def extraer_features(self, y, sr):
        if y is None:
            return None
        
        #TEMPO ( O RITMO)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_val = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])

        #BRILLO/VIBRA
        centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))

        #RUIDO/ INTENSIDAD (zero crossingrate)
        zcr = np.mean(librosa.feature.zero_crossing_rate(y))

        #TIMBRE/INSTRUMENTACION D. MFCC
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_means = np.mean(mfcc, axis=1) #ARRAY DE 13 VAL

        cromosoma = np.hstack([tempo_val, centroid, zcr, mfcc_means])
        return cromosoma
    

    def generar_cromosoma(self, url):
        y, sr = self._convertir_cancion(url)

        if y is None: 
            return None
        
        cromosoma = self.extraer_features(y, sr)
        return cromosoma