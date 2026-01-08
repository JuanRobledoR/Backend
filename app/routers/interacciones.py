from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.funciones_db import (
    registrar_like_db, obtener_likes_db, registrar_historial_db, 
    obtener_historial_db, crear_playlist_db, obtener_playlists_db, 
    eliminar_playlist_db, agregar_cancion_a_playlist_db,      
    obtener_canciones_playlist_db, eliminar_cancion_de_playlist_db,
    asegurar_cancion_existente, eliminar_like_db  
)
from app.schemas import LikeRequest, CancionBase 

router = APIRouter(prefix="/interacciones", tags=["Interacciones"])

class PlaylistCreate(BaseModel):
    id_usuario: int
    nombre: str

class AddToPlaylistRequest(BaseModel):
    id_playlist: int
    cancion: CancionBase

# Registra like e historial
@router.post("/like")
def dar_like(payload: LikeRequest):
    datos = payload.cancion.dict()
    id_cancion = registrar_like_db(payload.id_usuario, datos)
    
    if id_cancion:
        registrar_historial_db(payload.id_usuario, id_cancion, 'LIKE')

    return {"mensaje": "Like e historial registrados"}

# Registra dislike e historial
@router.post("/dislike")
def dar_dislike(payload: LikeRequest):
    datos = payload.cancion.dict()
    id_cancion = asegurar_cancion_existente(datos)

    if id_cancion:
        registrar_historial_db(payload.id_usuario, id_cancion, 'DISLIKE')
        
    return {"mensaje": "Dislike registrado en historial"}

# Retorna likes de usuario
@router.get("/mis-likes/{id_usuario}")
def ver_mis_likes(id_usuario: int):
    return obtener_likes_db(id_usuario)

# Elimina like específico
@router.delete("/like/{id_usuario}/{id_cancion}")
def quitar_like(id_usuario: int, id_cancion: int):
    exito = eliminar_like_db(id_usuario, id_cancion)
    if exito:
        return {"mensaje": "Like eliminado"}
    raise HTTPException(status_code=500, detail="Error eliminando like")

# Registra reproducción
@router.post("/historial/play")
def registrar_play(payload: LikeRequest):
    datos = payload.cancion.dict()
    id_cancion = asegurar_cancion_existente(datos)
    
    if id_cancion:
        registrar_historial_db(payload.id_usuario, id_cancion, 'PLAY')
        
    return {"status": "ok"}

# Obtiene historial de usuario
@router.get("/historial/{id_usuario}")
def ver_historial(id_usuario: int):
    return obtener_historial_db(id_usuario)

# Crea nueva playlist
@router.post("/playlist")
def nueva_playlist(p: PlaylistCreate):
    id_p = crear_playlist_db(p.id_usuario, p.nombre)
    if id_p:
        return {"id": id_p, "mensaje": "Playlist creada"}
    raise HTTPException(status_code=500, detail="Error creando playlist")

# Lista playlists de usuario
@router.get("/playlist/{id_usuario}")
def mis_playlists(id_usuario: int):
    return obtener_playlists_db(id_usuario)

# Elimina playlist completa
@router.delete("/playlist/{id_playlist}")
def borrar_playlist(id_playlist: int):
    eliminar_playlist_db(id_playlist)
    return {"mensaje": "Eliminada"}

# Obtiene canciones de playlist
@router.get("/playlist/{id_playlist}/tracks")
def ver_canciones_playlist(id_playlist: int):
    return obtener_canciones_playlist_db(id_playlist)

# Agrega canción a playlist
@router.post("/playlist/add")
def agregar_a_playlist(payload: AddToPlaylistRequest):
    datos = payload.cancion.dict()
    exito = agregar_cancion_a_playlist_db(payload.id_playlist, datos)
    if exito:
        return {"mensaje": "Agregada a playlist"}
    raise HTTPException(status_code=500, detail="Error agregando canción")

# Elimina canción de playlist
@router.delete("/playlist/{id_playlist}/track/{id_cancion}")
def eliminar_de_playlist(id_playlist: int, id_cancion: int):
    exito = eliminar_cancion_de_playlist_db(id_playlist, id_cancion)
    if exito:
        return {"mensaje": "Eliminada"}
    raise HTTPException(status_code=500, detail="Error eliminando")