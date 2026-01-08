import httpx
import asyncio
import random
from app.services.audio_analysis import AudioAnalysisService
from app.models.funciones_db import guardar_cancion_con_cromosoma, connection

# Verifica si la canción ya existe en la base de datos para evitar duplicados.
async def cancion_existe(id_externo, plataforma):
    cursor = connection.cursor()
    cursor.execute("SELECT 1 FROM Cancion WHERE id_externo = %s AND plataforma = %s", (str(id_externo), plataforma))
    existe = cursor.fetchone()
    cursor.close()
    return existe is not None

# Itera sobre categorías musicales, busca en Deezer, analiza el audio y guarda en DB hasta cumplir la meta.
async def procesar_poblacion_equitativa(categorias, limite_total=3000):
    analyzer = AudioAnalysisService()
    procesadas = 0
    meta_por_cat = limite_total // len(categorias)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for genero, terminos in categorias.items():
            cat_procesadas = 0
            print(f"\n--- 📂 Iniciando Categoría: {genero.upper()} (Meta: {meta_por_cat}) ---")
            
            while cat_procesadas < meta_por_cat:
                q = random.choice(terminos)
                offset = random.randint(0, 150)
                
                try:
                    resp = await client.get(f"https://api.deezer.com/search?q={q}&index={offset}&limit=50")
                    data = resp.json().get('data', [])
                    if not data: break

                    for track in data:
                        if cat_procesadas >= meta_por_cat or procesadas >= limite_total: break
                        if not track.get('preview'): continue
                        
                        if await cancion_existe(track['id'], "DEEZER"): continue

                        datos = {
                            "id_externo": str(track['id']), "plataforma": "DEEZER",
                            "titulo": track['title'], "artista": track['artist']['name'],
                            "imagen_url": track['album']['cover_xl'], "preview_url": track['preview']
                        }
                        
                        print(f"🧬 [{procesadas+1}/3000] Analizando {genero}: {datos['titulo']}...")
                        cromo_raw = analyzer.generar_cromosoma(datos['preview_url'])
                        
                        if cromo_raw is not None:
                            guardar_cancion_con_cromosoma(datos, cromo_raw.tolist())
                            procesadas += 1
                            cat_procesadas += 1
                
                except Exception as e:
                    print(f"🔥 Error en {genero}: {e}")
                    await asyncio.sleep(1)

# Punto de entrada principal que define las categorías y lanza el proceso de minería asíncrona.
async def main():
    categorias_musicales = {
        "metal": ["deathcore", "progressive metal", "black metal", "industrial metal", "groove metal"],
        "urbano": ["reggaeton 2025", "trap argentino", "dancehall", "dembow", "perreo"],
        "electronica": ["dark techno", "psytrance", "melodic house", "hardstyle", "synthwave"],
        "pop_indie": ["k-pop 2025", "indie pop", "dream pop", "j-rock", "bedroom pop"],
        "regional_latino": ["corridos tumbados", "salsa brava", "cumbia villera", "boleros", "mariachi"],
        "hip_hop": ["boom bap", "phonk drift", "uk drill", "lofi hip hop", "rap consciente"]
    }
    
    print("Iniciando Minería Equitativa de 3000 canciones)")
    await procesar_poblacion_equitativa(categorias_musicales, 3000)
    print("\n✅ Base de datos balanceada con 3000 canciones nuevas.")

if __name__ == "__main__":
    asyncio.run(main())