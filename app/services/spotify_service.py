import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import httpx


#Servicio de Spotify público
class SpotifyService:
    def __init__(self):

        self.sp = None
        
        CLIENT_ID='25cc72c68038426f9192994527a53bcf'.strip()
        CLIENT_SECRET='42940f807b904779ad446b079f29e35d'.strip()
        self.URL_DEEZER='https://api.deezer.com'

        #CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
        #CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
        #PLAYLIST_ID = "6GjULfC3dnq103KCta8plp"

        try:
            if not CLIENT_ID or not CLIENT_SECRET:
                raise ValueError("Las credenciales de Spotify no están configuradas correctamente.")
            else:
                auth_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            print(e)
            sp = None


    # ------------------------------------------------------------------------------------------ #
    #-------------------------- Funciones de Spotify ------------------------------------------- #
    # ------------------------------------------------------------------------------------------ #

    #Func enlistar canciones de una playlist pública
    def enlistar_playlist(self, PLAYLIST_ID):
        if not self.sp:
            return None
        try:
            resultado = self.sp.playlist_items(PLAYLIST_ID, limit=100)
            lista_completa_items = resultado['items']

            while resultado['next']:
                resultado = self.sp.next(resultado)
                lista_completa_items.extend(resultado['items'])

            # CAMBIO AQUÍ: No devolvemos solo el ID, devolvemos un diccionario con datos
            lista_canciones = []
            for item in lista_completa_items:
                track = item.get('track')
                if track and track.get('id'):
                    lista_canciones.append({
                        'id': track['id'],
                        'name': track['name'],
                        # Guardamos estructura compatible con tu main.py
                        'artists': [{'name': art['name']} for art in track['artists']]
                    })

            print(f"Playlist procesada: {len(lista_canciones)} canciones obtenidas.")
            return lista_canciones
        
        except Exception as e:
            print(e)
            return []
        


    def leer_datos_cancion(self, TRACK_ID):
        if not self.sp:
            return None
        try:
            resultado = self.sp.track(TRACK_ID)
            return resultado
        except Exception as e:
            print(e)
            return None
        
    
    def obtener_nombre_cancion(self, TRACK_ID):
        if not self.sp:
            return None
        try:
            track_info = self.sp.track(TRACK_ID)
            nombre_cancion = track_info.get('name')
            return nombre_cancion
        except Exception as e:
            print(e)
            return None
            

    def obtener_artista(self, TRACK_ID):
        if not self.sp:
            return None
        try:
            track_info = self.sp.track(TRACK_ID)
            artistas = track_info.get('artists', [])
            nombres_artistas = [artista['name'] for artista in artistas]
            return nombres_artistas
        except Exception as e:
            print(e)
            return None

    def obtener_url_preview(self, TRACK_ID):
        nombre_cancion = self.obtener_nombre_cancion(TRACK_ID)
        nombre_artista = self.obtener_artista(TRACK_ID)
        if not nombre_cancion or not nombre_artista:
            return None
        deezer_track_id = self.obtener_id_cancion_deezer(nombre_cancion, nombre_artista[0])
        if not deezer_track_id:
            return None
        preview_url = self.obtener_preview_por_id(deezer_track_id)
        return preview_url
    
    # ------------------------------------------------------------------------------------------ #
    #-------------------------- Funciones de Spotify ------------------------------------------- #
    # ------------------------------------------------------------------------------------------ #









    def obtener_id_cancion_deezer(self, nombre_cancion, nombre_artista):
        try:
            query = f'artist:"{nombre_artista}" track:"{nombre_cancion}"'
            url = f"{self.URL_DEEZER}/search"
            params = {'q': query, 'limit': 1, "order": "RATING_DESC"}
            response = httpx.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data and 'data' in data and len(data['data']) > 0:
                deezer_track_id = data['data'][0]['id']
                return deezer_track_id
            else:
                return None
        except Exception as e:
            print(e)
            return None
        
    def obtener_preview_por_id(self, deezer_track_id):
        try:
            url = f"{self.URL_DEEZER}/track/{deezer_track_id}"
            response = httpx.get(url)
            response.raise_for_status()
            data = response.json()

            preview_url = data.get('preview')
            return preview_url
        except Exception as e:
            print(e)
            return None
"""
    #Función inhabilitada por spotipy :c
    def obtener_audio_features(self, TRACK_ID):
        if not self.sp:
            return None
        try:
            resultado = self.sp.audio_features([TRACK_ID])
            return resultado
        except Exception as e:
            print(f"epa epa {e}")
            return None

    #Tampoco sirve esta 
    def obtener_preview_url(self, TRACK_ID):
        if not self.sp:
            return None
        try:
            resultado = self.sp.track(TRACK_ID)
            url_audio = resultado.get('preview_url')
            
            if url_audio:
                return url_audio
            else:
                return None
        except Exception as e:
            print(e)
            return None
"""  
