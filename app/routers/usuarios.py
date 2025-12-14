from fastapi import APIRouter, HTTPException
from app.schemas import UsuarioCreate, UsuarioResponse
from app.models.funciones_db import crear_usuario_db, obtener_usuario_por_id

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"]
)

@router.post("/registro", response_model=dict)
def registrar_usuario(usuario: UsuarioCreate):
    # Convertimos el modelo Pydantic a diccionario
    datos = usuario.dict()
    
    # Llamamos a la DB
    resultado = crear_usuario_db(datos)
    
    if resultado:
        return {"mensaje": "Usuario creado exitosamente", "id": resultado[0], "usuario": resultado[1]}
    else:
        # Si falla (ej. email repetido)
        raise HTTPException(status_code=400, detail="Error al crear usuario. Verifica que el email o usuario no existan ya.")

@router.get("/{id_usuario}", response_model=UsuarioResponse)
def leer_usuario(id_usuario: int):
    usuario_encontrado = obtener_usuario_por_id(id_usuario)
    
    if not usuario_encontrado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return usuario_encontrado