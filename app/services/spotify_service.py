import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

class SpotifyService:
    # Autentica el cliente usando credenciales hardcodeadas
    def __init__(self):
        self.sp = None
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

    # Obtiene todas las canciones de una playlist manejando paginación
    def enlistar_playlist(self, PLAYLIST_ID):
        if not self.sp: return []
        try:
            resultado = self.sp.playlist_items(PLAYLIST_ID, limit=100)
            lista_completa_items = resultado['items']

            while resultado['next']:
                resultado = self.sp.next(resultado)
                lista_completa_items.extend(resultado['items'])

            lista_canciones = []
            for item in lista_completa_items:
                track = item.get('track')
                if track and track.get('id') and track.get('name'):
                    lista_canciones.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artists': [{'name': art['name']} for art in track.get('artists', [])]
                    })

            print(f"✅ Playlist procesada: {len(lista_canciones)} semillas obtenidas.")
            return lista_canciones
        
        except Exception as e:
            print(f"Error enlistando playlist: {e}")
            return []

    # Retorna objeto track completo
    def leer_datos_cancion(self, TRACK_ID):
        if not self.sp: return None
        try: return self.sp.track(TRACK_ID)
        except: return None
        
    # Retorna solo el nombre de la canción
    def obtener_nombre_cancion(self, TRACK_ID):
        if not self.sp: return None
        try: return self.sp.track(TRACK_ID).get('name')
        except: return None
            
    # Retorna lista de nombres de artistas
    def obtener_artista(self, TRACK_ID):
        if not self.sp: return None
        try:
            track = self.sp.track(TRACK_ID)
            return [a['name'] for a in track.get('artists', [])]
        except: return None