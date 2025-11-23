import psycopg2

CONFIG = {
#sudo ss -lptn 'sport = :5432'
        'host' : '127.0.0.1',
        'port' : '5432',
        'user' : 'postgres',
        'password' : 'juanito123',
        'database' : 'beatmatchprueba01'    
}

try:
    connection = psycopg2.connect(**CONFIG)
    print("Conexion exitosa")

except Exception as e:
    print(e)

