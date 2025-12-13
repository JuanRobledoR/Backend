import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import httpx

class SpotifyService:
    def __init__(self):
        self.sp = None
        # RECOMENDACIÓN: Usa variables de entorno en producción, pero por ahora tus credenciales hardcodeadas funcionan.
        CLIENT_ID='25cc72c68038426f9192994527a53bcf'.strip()
        CLIENT_SECRET='42940f807b904779ad446b079f29e35d'.strip()

        try:
            if not CLIENT_ID or not CLIENT_SECRET:
                raise ValueError("Credenciales no configuradas.")
            else:
                auth_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            print(f"Error Auth Spotify: {e}")
            self.sp = None

    # --- FUNCIÓN PRINCIPAL PARA EL FEED ---
    def enlistar_playlist(self, PLAYLIST_ID):
        """Devuelve una lista de diccionarios con metadatos básicos para usar como semilla."""
        if not self.sp: return []
        try:
            resultado = self.sp.playlist_items(PLAYLIST_ID, limit=100)
            lista_completa_items = resultado['items']

            # Paginación (si la playlist es enorme)
            while resultado['next']:
                resultado = self.sp.next(resultado)
                lista_completa_items.extend(resultado['items'])

            lista_canciones = []
            for item in lista_completa_items:
                track = item.get('track')
                # Validación estricta para evitar errores si Spotify devuelve nulos
                if track and track.get('id') and track.get('name'):
                    lista_canciones.append({
                        'id': track['id'],
                        'name': track['name'],
                        # Estructura segura de artistas
                        'artists': [{'name': art['name']} for art in track.get('artists', [])]
                    })

            print(f"✅ Playlist procesada: {len(lista_canciones)} semillas obtenidas.")
            return lista_canciones
        
        except Exception as e:
            print(f"Error enlistando playlist: {e}")
            return []

    # --- HELPERS EXTRAS (Usados por otros endpoints) ---
    def leer_datos_cancion(self, TRACK_ID):
        if not self.sp: return None
        try: return self.sp.track(TRACK_ID)
        except: return None
        
    def obtener_nombre_cancion(self, TRACK_ID):
        if not self.sp: return None
        try: return self.sp.track(TRACK_ID).get('name')
        except: return None
            
    def obtener_artista(self, TRACK_ID):
        if not self.sp: return None
        try:
            track = self.sp.track(TRACK_ID)
            return [a['name'] for a in track.get('artists', [])]
        except: return None

    # El resto de funciones (obtener_url_preview, etc) las puedes dejar si las usas en endpoints antiguos,
    # pero el nuevo sistema de main.py usa Deezer directamente y no depende de ellas.