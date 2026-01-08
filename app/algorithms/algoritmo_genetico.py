import numpy as np
import random
from typing import List, Dict

class RealGeneticOptimizer:
    def __init__(self, song_pool: List[Dict], target_vibe: np.array, playlist_size: int = 10):
        self.pool = song_pool
        self.target = target_vibe
        self.playlist_size = playlist_size
        self.population_size = 40
        self.generations = 80
        self.mutation_rate = 0.15
        self.elitism_count = 2

    def _calcular_penalizacion_artistas(self, individual: List[Dict]) -> float:
        """Evita que el feed se llene del mismo artista"""
        artistas = [s.get('artista') for s in individual]
        conteo = {}
        for a in artistas:
            conteo[a] = conteo.get(a, 0) + 1
        return sum([(count - 1) * 0.2 for count in conteo.values()])

    def _calculate_fitness(self, individual: List[Dict]) -> float:
        if not individual: return 0.0
        
        matrix = np.array([np.array(s['cromosoma']) for s in individual])
        playlist_vibe = np.mean(matrix, axis=0)
        
        # --- AJUSTE PARA METAL ---
        # Le damos un peso masivo (3.0) a los MFCC (textura de guitarra) 
        # y bajamos el peso del tempo para que no lo confunda con Phonk
        weights = np.array([0.5, 1.0, 1.5] + [3.0] * 13) 
        max_vals = np.array([200, 5000, 1.0] + [250] * 13)
        
        target_n = self.target / max_vals
        vibe_n = playlist_vibe / max_vals
        
        diff = np.abs(target_n - vibe_n) * weights
        similarity = 1.0 - np.mean(diff)

        # Premio por distorsión (Energy)
        energy = np.mean([s['cromosoma'][1]/5000 + s['cromosoma'][2]/1.0 for s in individual]) / 2

        penalty = self._calcular_penalizacion_artistas(individual)
        
        return max(0.0, (similarity * 0.7) + (energy * 0.3) - penalty)

    def run(self):
        if len(self.pool) < self.playlist_size: return self.pool
        
        # Crear población inicial
        population = [random.sample(self.pool, self.playlist_size) for _ in range(self.population_size)]

        for _ in range(self.generations):
            population = sorted(population, key=lambda x: self._calculate_fitness(x), reverse=True)
            
            # Elitismo
            next_gen = population[:self.elitism_count]

            while len(next_gen) < self.population_size:
                p1, p2 = random.sample(population[:15], 2)
                # Crossover simple
                point = random.randint(1, self.playlist_size - 1)
                child = p1[:point] + p2[point:]
                # Mutación
                if random.random() < self.mutation_rate:
                    child[random.randint(0, self.playlist_size-1)] = random.choice(self.pool)
                
                next_gen.append(child[:self.playlist_size])
            
            population = next_gen

        return population[0]