import spotipy
import random
import asyncio
import numpy as np
import httpx
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional, Union

# Importaciones internas
from app.routers import usuarios, interacciones, auth
from app.services.spotify_service import SpotifyService
from app.services.audio_analysis import AudioAnalysisService  
from app.algorithms.algoritmo_genetico import RealGeneticOptimizer
from app.algorithms.pseudogenetico import GeneticOptimizer
from app.models.funciones_db import connection
from app.schemas import LikeRequest, CancionBase
from app.models.funciones_db import (
    crear_usuario_db, contar_semillas_usuario, guardar_cancion_con_cromosoma, 
    registrar_semilla_db, registrar_like_db, crear_playlist_db, 
    agregar_cancion_a_playlist_db, obtener_likes_db, obtener_canciones_playlist_db
)

load_dotenv()

# Inicializa app
app = FastAPI(
    title="BeatMatch API",
    description="Backend para descubrimiento de música usando IA",
    version="1.0.0"
)

# Configura CORS
origins = ["https://frontend-r4hr.onrender.com",
           "http://localhost:5173",] 
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra routers
app.include_router(usuarios.router)
app.include_router(interacciones.router)
app.include_router(auth.router)

# ---------------------------------------------------- #
# --------------- MODELOS DE DATOS ------------------- #
# ---------------------------------------------------- #

class TrackCandidate(BaseModel):
    id: Union[str, int]
    titulo: str
    preview_url: str
    artista: str 
    imagen: str  

class FeedRequest(BaseModel):
    playlist_id: str
    limit: int = 20
    seen_ids: List[Union[str, int]] = [] 

class PlaylistRequest(BaseModel):
    target_track_url: str       
    candidates: List[TrackCandidate]

class SavePlaylistRequest(BaseModel):
    track_ids: List[str] 
    name: str = "BeatMatch Discovery"
    description: str = "Playlist generada con BeatMatch App"

class SmartPlaylistRequest(BaseModel):
    id_usuario: int
    nombre_playlist: str = "Playlist IA Generada"
    semilla_id: Optional[str] = None 

class ImportSpotifyRequest(BaseModel):
    id_usuario: int
    spotify_playlist_id: str

class CompletePlaylistRequest(BaseModel):
    id_usuario: int
    id_playlist: int

# ---------------------------------------------------- #
# --------------- UTILIDADES SPOTIFY ----------------- #
# ---------------------------------------------------- #

# Health check
@app.get("/")
def inicio():
    return "BeatMatch funcionando"

# Obtiene tracks Spotify
@app.get("/playlist-tracks/{PLAYLIST_ID}")
def top_tracks(PLAYLIST_ID: str):
    spotify_service = SpotifyService()
    return spotify_service.enlistar_playlist(PLAYLIST_ID)

# Detalle canción Spotify
@app.get("/datos-cancion/{TRACK_ID}")
def datos_cancion(TRACK_ID: str):
    spotify_service = SpotifyService()
    return spotify_service.leer_datos_cancion(TRACK_ID)

# Exporta playlist usuario
@app.post("/crear-playlist-spotify")
def crear_playlist_usuario(payload: SavePlaylistRequest):
    try:
        sp_service = SpotifyService()
        user_id = sp_service.sp.current_user()['id']
        
        playlist = sp_service.sp.user_playlist_create(
            user=user_id, name=payload.name, public=False, description=payload.description
        )
        
        track_uris = [f"spotify:track:{tid}" if "spotify:track:" not in tid else tid for tid in payload.track_ids]
        
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            sp_service.sp.playlist_add_items(playlist_id=playlist['id'], items=batch)
            
        return {"status": "success", "playlist_url": playlist['external_urls']['spotify']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Importa playlist Spotify
@app.post("/importar-playlist-spotify")
async def importar_spotify(payload: ImportSpotifyRequest):
    try:
        sp = SpotifyService()
        analyzer = AudioAnalysisService()

        tracks_spotify = sp.enlistar_playlist(payload.spotify_playlist_id)
        if not tracks_spotify:
            raise HTTPException(status_code=404, detail="No se encontraron canciones")

        nombre_pl = f"Importada de Spotify ({len(tracks_spotify)} canciones)"
        id_playlist_nueva = crear_playlist_db(payload.id_usuario, nombre_pl)

        count_procesadas = 0
        semillas_actuales = contar_semillas_usuario(payload.id_usuario)

        async with httpx.AsyncClient() as client:
            for t in tracks_spotify:
                titulo = t['name']
                artista = t['artists'][0]['name'] if t['artists'] else "Unknown"
                
                datos_cancion = {
                    "id_externo": t['id'], "plataforma": "SPOTIFY",
                    "titulo": titulo, "artista": artista,
                    "imagen_url": "", "preview_url": "" 
                }

                cromosoma = None
                try:
                    q = f'artist:"{artista}" track:"{titulo}"'
                    resp = await client.get("https://api.deezer.com/search", params={"q": q, "limit": 1})
                    data = resp.json()
                    
                    if data.get('data'):
                        match = data['data'][0]
                        datos_cancion['imagen_url'] = match['album']['cover_xl']
                        datos_cancion['preview_url'] = match['preview']
                        
                        if datos_cancion['preview_url']:
                            cromo_raw = analyzer.generar_cromosoma(datos_cancion['preview_url'])
                            if cromo_raw is not None:
                                cromosoma = cromo_raw.tolist()
                except Exception as e:
                    print(f"Error análisis: {e}")

                id_cancion_db = guardar_cancion_con_cromosoma(datos_cancion, cromosoma)

                if id_cancion_db:
                    agregar_cancion_a_playlist_db(id_playlist_nueva, datos_cancion)
                    if semillas_actuales < 10:
                        registrar_semilla_db(payload.id_usuario, id_cancion_db)
                        semillas_actuales += 1
                    count_procesadas += 1

        return {"mensaje": "Importación completada", "nuevas": count_procesadas}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------- #
# --------------- UTILIDADES DEEZER ------------------ #
# ---------------------------------------------------- #

# Analiza audio URL
@app.get("/features/") 
def get_features(url_cancion: str): 
    audio_analisis = AudioAnalysisService()
    resultado = audio_analisis.generar_cromosoma(url_cancion)
    return {"cromosoma": resultado.tolist()} if resultado is not None else {"error": "Error procesando audio"}

# Busca en Deezer
@app.get("/buscar")
async def buscar_cancion(q: str):
    if not q: return []
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.deezer.com/search?q={q}&limit=5")
        data = response.json()
        
    return [{
        "id": t["id"], "titulo": t["title"], "artista": t["artist"]["name"],
        "imagen": t["album"]["cover_xl"], "preview": t["preview"]
    } for t in data.get("data", [])]

# ---------------------------------------------------- #
# ---------------- SISTEMA FEED ---------------------- #
# ---------------------------------------------------- #

# Genera feed infinito
@app.post("/feed-playlist")
async def feed_playlist_infinito(payload: FeedRequest):
    try:
        spotify_service = SpotifyService()
        tracks_origen = spotify_service.enlistar_playlist(payload.playlist_id)
        if not tracks_origen: return {"error": "Playlist vacía"}

        blacklist_ids = set(str(sid) for sid in payload.seen_ids)
        resultados_finales = []
        conteo_artistas = {}
        intentos = 0
        
        async with httpx.AsyncClient(timeout=25.0) as client:
            while len(resultados_finales) < payload.limit and intentos < 15:
                semilla = random.choice(tracks_origen)
                artista = semilla['artists'][0]['name'] if semilla.get('artists') else ""
                
                query = f'{artista} {semilla.get("name", "")}'
                search_res = await client.get("https://api.deezer.com/search", params={"q": query, "limit": 1})
                s_data = search_res.json()
                
                if not s_data.get('data'):
                    intentos += 1; continue 
                
                dz_track = s_data['data'][0]
                
                # Estrategia mixta: Related o Top
                candidatos = []
                rel_res = await client.get(f"https://api.deezer.com/track/{dz_track['id']}/related")
                rel_data = rel_res.json()
                
                if rel_data.get('data'):
                    candidatos = rel_data['data']
                else:
                    top_res = await client.get(f"https://api.deezer.com/artist/{dz_track['artist']['id']}/top?limit=30")
                    top_data = top_res.json()
                    candidatos = top_data.get('data', [])

                random.shuffle(candidatos)
                
                for t in candidatos:
                    if len(resultados_finales) >= payload.limit: break
                    tid = str(t['id'])
                    tart = t['artist']['name']
                    
                    if tid in blacklist_ids: continue
                    if conteo_artistas.get(tart, 0) >= 2: continue 
                    
                    resultados_finales.append({
                        "id": t["id"], "titulo": t["title"], "artista": tart,
                        "imagen": t["album"]["cover_xl"], "preview": t["preview"],
                    })
                    
                    blacklist_ids.add(tid)
                    conteo_artistas[tart] = conteo_artistas.get(tart, 0) + 1
                
                intentos += 1
        return resultados_finales

    except Exception:
        return []

# ---------------------------------------------------- #
# --------------- ALGORITMO GENÉTICO ----------------- #
# ---------------------------------------------------- #

# Ejecuta optimizador genético
@app.post("/generar-playlist-inteligente")
async def generar_playlist_inteligente(payload: PlaylistRequest):
    analyzer = AudioAnalysisService()
    target_cromosoma = analyzer.generar_cromosoma(payload.target_track_url)
    
    if target_cromosoma is None: return {"error": "Error analizando target"}

    processed_candidates = []
    for track in payload.candidates:
        if track.preview_url:
            try:
                cromo = analyzer.generar_cromosoma(track.preview_url)
                if cromo is not None:
                    processed_candidates.append({
                        "id": track.id, "titulo": track.titulo, "preview": track.preview_url,
                        "artista": track.artista, "imagen": track.imagen, "cromosoma": cromo.tolist()
                    })
            except: pass
                
    if len(processed_candidates) < 5: return {"error": "Insuficientes candidatos"}

    optimizer = RealGeneticOptimizer(song_pool=processed_candidates, target_vibe=target_cromosoma)
    mejor_playlist = optimizer.run()
    
    return {"playlist_generada": [{k: v for k, v in t.items() if k != 'cromosoma'} for t in mejor_playlist]}

# Crea playlist automática
@app.post("/crear-playlist-inteligente-auto")
async def auto_smart_playlist(payload: SmartPlaylistRequest):
    id_pl = crear_playlist_db(payload.id_usuario, payload.nombre_playlist)
    analyzer = AudioAnalysisService()
    
    likes = obtener_likes_db(payload.id_usuario)
    if not payload.semilla_id and likes:
        target_cromosoma = analyzer.generar_cromosoma(likes[0]['preview'])
        query_artist = likes[0]['artista']
    else:
        query_artist = "Daft Punk" 
        target_cromosoma = np.random.rand(16)

    candidatos = []
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.deezer.com/search?q=artist:'{query_artist}'&limit=50")
        data = resp.json().get('data', [])
        
        for track in data[:30]: 
            if track['preview']:
                cromo = analyzer.generar_cromosoma(track['preview'])
                if cromo is not None:
                    candidatos.append({
                        "id_externo": str(track["id"]), "titulo": track["title"],
                        "artista": track["artist"]["name"], "imagen_url": track["album"]["cover_xl"],
                        "preview_url": track["preview"], "cromosoma": cromo.tolist(), "plataforma": "DEEZER"
                    })

    if len(candidatos) > 5:
        optimizer = GeneticOptimizer(candidatos, target_cromosoma.tolist(), 20)
        seleccion = optimizer.run()
    else:
        seleccion = candidatos

    for track in seleccion:
        agregar_cancion_a_playlist_db(id_pl, track)

    return {"mensaje": "Playlist generada", "total": len(seleccion)}

# Rellena playlist existente
@app.post("/completar-playlist-ia")
async def completar_playlist_existente(payload: CompletePlaylistRequest):
    analyzer = AudioAnalysisService()
    canciones = obtener_canciones_playlist_db(payload.id_playlist)
    target_cromosoma = None
    query_artist = "Daft Punk" 
    
    # Estrategia A: Audio nativo
    validas = [c for c in canciones if c['preview']]
    if validas:
        cromosomas = []
        for c in validas[:5]: 
            cromo = analyzer.generar_cromosoma(c['preview'])
            if cromo is not None: cromosomas.append(cromo)
        if cromosomas:
            target_cromosoma = np.mean(cromosomas, axis=0)
            query_artist = validas[0]['artista']

    # Estrategia B: Referencia externa
    if target_cromosoma is None and canciones:
        ref = canciones[0]
        async with httpx.AsyncClient() as client:
            q = f"{ref['artista']} {ref['titulo']}"
            resp = await client.get(f"https://api.deezer.com/search?q={q}&limit=1")
            d = resp.json().get('data')
            if d and d[0].get('preview'):
                target_cromosoma = analyzer.generar_cromosoma(d[0]['preview'])
                query_artist = ref['artista']

    # Estrategia C: Likes
    if target_cromosoma is None:
        likes = obtener_likes_db(payload.id_usuario)
        if likes and likes[0].get('preview'):
            target_cromosoma = analyzer.generar_cromosoma(likes[0]['preview'])
            query_artist = likes[0]['artista']
    
    if target_cromosoma is None: raise HTTPException(status_code=400, detail="Sin datos para IA")

    candidatos = []
    ids_ex = set(str(c['id_externo']) for c in canciones)

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.deezer.com/search?q=artist:'{query_artist}'&limit=50")
        raw = resp.json().get('data', [])
        
        for t in raw:
            if str(t['id']) in ids_ex: continue 
            if t['preview']:
                cromo = analyzer.generar_cromosoma(t['preview'])
                if cromo is not None:
                    candidatos.append({
                        "id_externo": str(t["id"]), "titulo": t["title"], "artista": t["artist"]["name"],
                        "imagen_url": t["album"]["cover_xl"], "preview_url": t["preview"],
                        "cromosoma": cromo.tolist(), "plataforma": "DEEZER"
                    })
                if len(candidatos) >= 15: break 

    if not candidatos: return {"mensaje": "Sin candidatos"}

    optimizer = GeneticOptimizer(candidatos, target_cromosoma.tolist(), 5)
    seleccion = optimizer.run()

    count = 0
    for t in seleccion:
        if agregar_cancion_a_playlist_db(payload.id_playlist, t): count += 1

    return {"mensaje": "Completado", "agregadas": count}

# Refresca URLs Deezer
async def refrescar_links_deezer(lista_canciones: list):
    async with httpx.AsyncClient(timeout=10.0) as client:
        tareas = [client.get(f"https://api.deezer.com/track/{s.get('id_externo')}") for s in lista_canciones]
        respuestas = await asyncio.gather(*tareas, return_exceptions=True)
        
        for i, resp in enumerate(respuestas):
            if isinstance(resp, httpx.Response) and resp.status_code == 200:
                lista_canciones[i]['preview'] = resp.json().get('preview')
    return lista_canciones

# Generación híbrida IA (Core)
@app.get("/generar-smart-playlist/{id_usuario}")
async def endpoint_ia_real(id_usuario: int, exclude: List[int] = Query([])):
    cursor = connection.cursor()
    try:
        # Obtiene target promedio
        cursor.execute("""
            SELECT c.cromosoma FROM Me_Gusta m 
            JOIN Cancion c ON m.id_cancion = c.id_cancion 
            WHERE m.id_usuario = %s AND c.cromosoma IS NOT NULL 
            ORDER BY m.fecha_like DESC LIMIT 10
        """, (id_usuario,))
        semillas = cursor.fetchall() or []
        
        if not semillas:
             cursor.execute("""
                SELECT c.cromosoma FROM Usuario_Semilla us 
                JOIN Cancion c ON us.id_cancion = c.id_cancion 
                WHERE us.id_usuario = %s AND c.cromosoma IS NOT NULL LIMIT 10
            """, (id_usuario,))
             semillas = cursor.fetchall()

        if not semillas: raise HTTPException(status_code=400, detail="Faltan datos")

        vectores = [np.array(s[0]) for s in semillas]
        target_vibe = np.mean(vectores, axis=0)

        # Filtra exclusiones
        cursor.execute("SELECT id_cancion FROM Historial WHERE id_usuario = %s UNION SELECT id_cancion FROM Me_Gusta WHERE id_usuario = %s", (id_usuario, id_usuario))
        lista_negra = list(set([r[0] for r in cursor.fetchall()] + exclude))

        # Recupera pool masivo
        query = "SELECT id_cancion, titulo, artista, imagen_url, preview_url, cromosoma, id_externo FROM Cancion WHERE cromosoma IS NOT NULL"
        if lista_negra: query += f" AND id_cancion NOT IN ({','.join(map(str, lista_negra))})"
        
        cursor.execute(query + " ORDER BY RANDOM() LIMIT 1000")
        rows = cursor.fetchall()
        
        candidates_pool = [{"id": r[0], "titulo": r[1], "artista": r[2], "imagen": r[3], "preview": r[4], "cromosoma": r[5], "id_externo": r[6]} for r in rows]

        # Filtro matemático previo
        scored = []
        weights = np.array([0.8, 1.0, 1.0] + [2.5] * 13)
        max_vals = np.array([200.0, 5000.0, 1.0] + [200.0] * 13)
        target_n = target_vibe / (max_vals + 1e-6)

        for s in candidates_pool:
            dist = np.linalg.norm((target_n - (np.array(s['cromosoma']) / (max_vals + 1e-6))) * weights)
            scored.append((s, dist))
        
        scored.sort(key=lambda x: x[1])
        top_100 = [x[0] for x in scored[:100]]

        # Ejecuta genético
        optimizer = RealGeneticOptimizer(top_100, target_vibe, 10)
        playlist = optimizer.run()
        
        resultado = [{k: v for k, v in s.items() if k != 'cromosoma'} for s in playlist]
        return {"playlist_evolucionada": await refrescar_links_deezer(resultado)}

    finally:
        cursor.close()

# ---------------------------------------------------- #
# --------------- ONBOARDING & ADMIN ----------------- #
# ---------------------------------------------------- #

# Check onboarding
@app.get("/usuarios/check-onboarding/{id_usuario}")
def check_onboarding(id_usuario: int):
    count = contar_semillas_usuario(id_usuario) 
    return {"completado": count >= 10, "faltantes": max(0, 10 - count)}

# Registra semilla
@app.post("/usuarios/registrar-semilla")
async def registrar_semilla(payload: LikeRequest):
    analyzer = AudioAnalysisService()
    cromosoma = None
    if payload.cancion.preview_url:
        cromo_raw = analyzer.generar_cromosoma(payload.cancion.preview_url)
        if cromo_raw is not None: cromosoma = cromo_raw.tolist()

    id_cancion = guardar_cancion_con_cromosoma(payload.cancion.dict(), cromosoma)
    
    if id_cancion:
        registrar_semilla_db(payload.id_usuario, id_cancion)
        registrar_like_db(payload.id_usuario, payload.cancion.dict())
        return {"mensaje": "Semilla registrada", "total": contar_semillas_usuario(payload.id_usuario)}
    
    raise HTTPException(status_code=500, detail="Error DB")

# Elimina semilla
@app.delete("/usuarios/eliminar-semilla")
async def eliminar_semilla(data: dict):
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT id_cancion FROM Cancion WHERE id_externo = %s", (data.get("id_externo"),))
        res = cursor.fetchone()
        if res:
            cursor.execute("DELETE FROM Usuario_Semilla WHERE id_usuario = %s AND id_cancion = %s", (data.get("id_usuario"), res[0]))
            connection.commit()
        
        cursor.execute("SELECT COUNT(*) FROM Usuario_Semilla WHERE id_usuario = %s", (data.get("id_usuario"),))
        return {"total": cursor.fetchone()[0]}
    finally:
        cursor.close()

# Obtiene semillas
@app.get("/usuarios/semillas/{id_usuario}")
async def obtener_semillas_usuario(id_usuario: int):
    cursor = connection.cursor()
    try:
        cursor.execute("""
            SELECT c.id_externo, c.titulo, c.artista, c.imagen_url, c.preview_url 
            FROM Usuario_Semilla us JOIN Cancion c ON us.id_cancion = c.id_cancion
            WHERE us.id_usuario = %s
        """, (id_usuario,))
        return [{"id": r[0], "titulo": r[1], "artista": r[2], "imagen": r[3], "preview": r[4]} for r in cursor.fetchall()]
    finally:
        cursor.close()

# Estadísticas admin
@app.get("/admin/stats")
def get_admin_stats():
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM Usuario")
    t_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Cancion")
    t_songs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Cancion WHERE cromosoma IS NOT NULL")
    t_ia = cursor.fetchone()[0]
    cursor.execute("SELECT titulo, artista, plataforma FROM Cancion ORDER BY id_cancion DESC LIMIT 5")
    recent = [{"titulo": r[0], "artista": r[1], "plataforma": r[2]} for r in cursor.fetchall()]
    cursor.close()
    return {"usuarios": t_users, "canciones_totales": t_songs, "canciones_ia": t_ia, "recientes": recent}

# Clasificar arquetipops
def calcular_etiqueta_vibe(target_vector):
    """
    Compara el vector del usuario con arquetipos predefinidos.
    Estos valores son aproximados (Tempo, Centroid, ZCR, MFCC1...)
    """
    import numpy as np
    
    # 1. Definir Arquetipos
    # Formato: [Tempo, Centroid, ZCR, ...MFCCs]
    # Nota: Los valores deben estar en la misma escala que AudioAnalysisService
    
    arquetipos = {
        "Phonk / Industrial": np.array([135.0, 3000.0, 0.15] + [0]*13), # Rápido, Ruidoso
        "Reggaeton / Urbano": np.array([95.0, 1500.0, 0.05] + [0]*13),  # Lento, Bajo profundo
        "Metal / Hardcore":   np.array([160.0, 4500.0, 0.25] + [0]*13), # Muy rápido, Muy ruidoso
        "Pop / Dance":        np.array([120.0, 2500.0, 0.08] + [0]*13), # Estándar
        "Lo-Fi / Chill":      np.array([80.0, 1000.0, 0.02] + [0]*13),  # Lento, Suave
        "Electronic / House": np.array([128.0, 3500.0, 0.10] + [0]*13)
    }
    
    user_vec = np.array(target_vector)
    
    # Normalización simple para comparar (BPM pesa menos, Timbre pesa más)
    weights = np.array([0.5, 1.0, 2.0] + [0.1]*13) 
    
    mejor_genero = "Indefinido"
    menor_distancia = float('inf')
    
    for genero, vector_arq in arquetipos.items():
        # (Tempo, Centroid, ZCR)
        dist = np.linalg.norm((user_vec[:3] - vector_arq[:3]) * weights[:3])
        
        if dist < menor_distancia:
            menor_distancia = dist
            mejor_genero = genero
            
    # porcentaje de certeza
    # Si la distancia es 0, certeza es 100%. Si es muy alta, baja.
    certeza = max(10, int(100 - (menor_distancia / 50)))
    
    return mejor_genero, certeza

@app.get("/usuarios/perfil-vibe/{id_usuario}")
def obtener_perfil_vibe(id_usuario: int):
    cursor = connection.cursor()
    try:
        # 1. últimos 20 likes para promediar
        cursor.execute("""
            SELECT c.cromosoma FROM Me_Gusta m 
            JOIN Cancion c ON m.id_cancion = c.id_cancion 
            WHERE m.id_usuario = %s AND c.cromosoma IS NOT NULL 
            ORDER BY m.fecha_like DESC LIMIT 20
        """, (id_usuario,))
        rows = cursor.fetchall()
        
        if not rows:
            return {"vibe": "Explorador Novato", "score": 0}
            
        # 2. Promedio
        vectores = [np.array(r[0]) for r in rows]
        user_target = np.mean(vectores, axis=0)
        
        # 3. Clasificación
        genero, score = calcular_etiqueta_vibe(user_target)
        
        return {"vibe": genero, "score": score}
        
    except Exception as e:
        print(f"Error vibe: {e}")
        return {"vibe": "Desconocido", "score": 0}
    finally:
        cursor.close()