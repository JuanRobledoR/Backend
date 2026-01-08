import requests
import librosa
import numpy as np
import tempfile
import os
from app.services.spotify_service import SpotifyService

class AudioAnalysisService:
    def __init__(self):
        pass

    # Descarga el MP3 temporalmente y carga la onda con Librosa
    def _convertir_cancion(self, cancion_URL):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(cancion_URL, headers=headers)
            r.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(r.content)
                temp_path = temp_file.name

            try:
                y, sr = librosa.load(temp_path, duration=30)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            return y, sr
        
        except Exception as e:
            print(e)
            return None, None

    # Extrae Tempo, Centroide, ZCR y MFCCs (16 floats total)
    def extraer_features(self, y, sr):
        if y is None:
            return None
        
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_val = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])

        centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        zcr = np.mean(librosa.feature.zero_crossing_rate(y))

        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_means = np.mean(mfcc, axis=1)

        cromosoma = np.hstack([tempo_val, centroid, zcr, mfcc_means])
        return cromosoma
    
    # Orquesta la descarga y análisis para retornar el vector final
    def generar_cromosoma(self, url):
        y, sr = self._convertir_cancion(url)

        if y is None: 
            return None
        
        cromosoma = self.extraer_features(y, sr)
        return cromosoma