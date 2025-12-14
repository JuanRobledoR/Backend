from pydantic import BaseModel, EmailStr
from typing import Optional

# Base para compartir campos comunes
class UsuarioBase(BaseModel):
    nombre_usuario: str
    apellido_paterno: str
    apellido_materno: Optional[str] = None
    email: EmailStr
    usuario: str # El username o nickname
    genero: bool # True: Hombre, False: Mujer (según tu tabla boolean)

# Esto es lo que recibimos al CREAR (incluye password)
class UsuarioCreate(UsuarioBase):
    contrasena: str

# Esto es lo que devolvemos al frontend (SIN password para seguridad)
class UsuarioResponse(UsuarioBase):
    id_usuario: int
    tipo_usuario: bool

    class Config:
        from_attributes = True

class CancionBase(BaseModel):
    id_externo: str       # ID de Spotify/Deezer
    plataforma: str       # 'SPOTIFY' o 'DEEZER'
    titulo: str
    artista: str
    album: Optional[str] = None
    imagen_url: Optional[str] = None
    preview_url: Optional[str] = None

class LikeRequest(BaseModel):
    id_usuario: int
    cancion: CancionBase