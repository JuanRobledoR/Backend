import numpy as np
import random
from typing import List, Dict

class RealGeneticOptimizer:
    # Inicializa el optimizador con el pool de canciones, el vector objetivo (vibe) y parámetros genéticos.
    def __init__(self, song_pool: List[Dict], target_vibe: np.array, playlist_size: int = 10):
        self.pool = song_pool
        self.target = target_vibe
        self.playlist_size = playlist_size
        self.population_size = 50 
        self.generations = 100
        self.mutation_rate = 0.1
        self.elitism_count = 5

    # Calcula una penalización acumulativa para evitar que el mismo artista domine la playlist (max 2 canciones).
    def _calcular_penalizacion_artistas(self, individual: List[Dict]) -> float:
        artistas = [s.get('artista') for s in individual]
        conteo = {}
        penalty = 0.0
        for a in artistas:
            count = conteo.get(a, 0) + 1
            conteo[a] = count
            if count > 2:
                penalty += 0.5 
        return penalty

    # Evalúa la calidad de una playlist comparando su promedio de audio con el target, aplicando pesos a los MFCC.
    def _calculate_fitness(self, individual: List[Dict]) -> float:
        if not individual: return 0.0
        
        matrix = np.array([np.array(s['cromosoma']) for s in individual])
        playlist_vibe = np.mean(matrix, axis=0)
        
        # Valores máximos teóricos para normalizar los vectores de audio
        max_vals = np.array([200.0, 5000.0, 1.0] + [200.0] * 13)
        
        target_n = self.target / (max_vals + 1e-6)
        vibe_n = playlist_vibe / (max_vals + 1e-6)
        
        # Pesos para dar prioridad al timbre/género sobre el tempo
        weights = np.array([0.8, 1.0, 1.0] + [2.5] * 13) 
        
        distancia = np.linalg.norm((target_n - vibe_n) * weights)
        
        similarity = 1.0 / (1.0 + distancia)

        penalty = self._calcular_penalizacion_artistas(individual)
        
        return max(0.0, similarity - penalty)

    # Genera un individuo aleatorio (playlist) a partir del pool disponible para iniciar la población.
    def create_individual(self):
        if len(self.pool) <= self.playlist_size:
            return self.pool
        return random.sample(self.pool, self.playlist_size)

    # Ejecuta el ciclo evolutivo completo: selección, elitismo, cruce y mutación para optimizar la playlist.
    def run(self):
        if len(self.pool) < self.playlist_size: 
            return self.pool
        
        population = [self.create_individual() for _ in range(self.population_size)]

        best_global = None
        best_fitness = -1.0

        for _ in range(self.generations):
            population_with_fitness = [(ind, self._calculate_fitness(ind)) for ind in population]
            population_with_fitness.sort(key=lambda x: x[1], reverse=True)
            
            current_best = population_with_fitness[0]
            if current_best[1] > best_fitness:
                best_fitness = current_best[1]
                best_global = current_best[0]

            # Conservamos los mejores individuos sin cambios (Elitismo)
            survivors = [ind for ind, fit in population_with_fitness[:self.elitism_count]]
            
            # Generamos nueva descendencia hasta llenar la población
            while len(survivors) < self.population_size:
                parent1 = random.choice(population_with_fitness[:20])[0]
                parent2 = random.choice(population_with_fitness[:20])[0]
                
                point = random.randint(1, self.playlist_size - 1)
                child = parent1[:point] + parent2[point:]
                
                # Probabilidad de mutar una canción por otra del pool
                if random.random() < self.mutation_rate:
                    idx = random.randint(0, self.playlist_size - 1)
                    child[idx] = random.choice(self.pool)
                
                survivors.append(child[:self.playlist_size])
            
            population = survivors

        return best_global if best_global else population[0]