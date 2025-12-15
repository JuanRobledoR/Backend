from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
# Asegúrate de tener esta función en funciones_db.py (paso 3 abajo)
from app.models.funciones_db import crear_usuario_db, verificar_credenciales_db

router = APIRouter(
    prefix="/auth",
    tags=["Autenticacion"]
)

# Esquemas de datos (Lo que React te envía)
class LoginSchema(BaseModel):
    username: str
    password: str

class RegisterSchema(BaseModel):
    username: str
    email: str
    password: str

# --- ENDPOINT LOGIN ---
@router.post("/login")
def login(datos: LoginSchema):
    # Verifica en base de datos
    usuario_valido = verificar_credenciales_db(datos.username, datos.password)
    
    if not usuario_valido:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    
    # Devuelve el ID para que React sepa quién eres
    return {
        "id_usuario": usuario_valido['id_usuario'],
        "username": usuario_valido['username'],
        "token": "token-simulado-123" 
    }

# --- ENDPOINT REGISTRO ---
@router.post("/register")
def register(datos: RegisterSchema):
    # Crea el diccionario para tu función de DB existente
    nuevo_usuario = {
        "nombre_usuario": datos.username, 
        "apellido_paterno": "",
        "apellido_materno": "",
        "email": datos.email,
        "usuario": datos.username,
        "contrasena": datos.password,
        "genero": True 
    }
    
    res = crear_usuario_db(nuevo_usuario)
    if not res:
        raise HTTPException(status_code=400, detail="El usuario o email ya existe")
    
    return {
        "id_usuario": res[0],
        "username": res[1],
        "token": "token-simulado-123"
    }