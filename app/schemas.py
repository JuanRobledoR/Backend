from pydantic import BaseModel, EmailStr
from typing import Optional

# Campos base compartidos de Usuario
class UsuarioBase(BaseModel):
    nombre_usuario: str
    apellido_paterno: str
    apellido_materno: Optional[str] = None
    email: EmailStr
    usuario: str 
    genero: bool 

# Schema para registro (incluye password)
class UsuarioCreate(UsuarioBase):
    contrasena: str

# Schema de respuesta pública (sin password)
class UsuarioResponse(UsuarioBase):
    id_usuario: int
    tipo_usuario: bool

    class Config:
        from_attributes = True

# Estructura estandarizada de canción
class CancionBase(BaseModel):
    id_externo: str       
    plataforma: str       
    titulo: str
    artista: str
    album: Optional[str] = None
    imagen_url: Optional[str] = None
    preview_url: Optional[str] = None

# Payload para interacciones de usuario
class LikeRequest(BaseModel):
    id_usuario: int
    cancion: CancionBase