import numpy as np
import random
from typing import List, Dict

class GeneticOptimizer:
    def __init__(self, population_data: List[Dict], target_chromosome: List[float], target_size: int = 5):
        """
        :param population_data: Lista de dicts. Cada dict DEBE tener la key 'cromosoma' (lista de 16 floats) y 'id'.
        :param target_chromosome: El cromosoma de la canción base (la "semilla" de la playlist).
        :param target_size: El número de canciones que quieres en la playlist final (Default 5, pero ahora soporta dinámico).
        """
        self.candidates = population_data
        self.target = np.array(target_chromosome)
        
        # AHORA ES DINÁMICO (Lo que le mandes desde el endpoint)
        self.playlist_size = target_size   
        
        self.population_size = 20 # Individuos en la población
        self.generations = 50     # Iteraciones
        
        # Vector de Normalización aproximado para tus 16 features:
        # [BPM, Centroid, ZCR, MFCC... ]
        # Esto evita que el Centroid (valor ~2000) opaque al resto.
        self.max_vals = np.array([
            200.0,   # BPM Max
            5000.0,  # Centroid Max
            1.0,     # ZCR Max
            # Los MFCC suelen variar entre -200 y 200, usamos 200 como referencia de magnitud
            *[200.0]*13 
        ])

    def normalize(self, vector):
        """Divide cada valor por su máximo teórico para tener todo entre -1 y 1 aprox."""
        v = np.array(vector)
        # Evitamos división por cero
        return v / (self.max_vals + 1e-6)

    def cosine_similarity(self, vec_a, vec_b):
        """Calcula qué tan parecidos son dos vectores (1 = idénticos, 0 = nada que ver)"""
        a_norm = self.normalize(vec_a)
        b_norm = self.normalize(vec_b)
        
        dot = np.dot(a_norm, b_norm)
        norm_a = np.linalg.norm(a_norm)
        norm_b = np.linalg.norm(b_norm)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def create_individual(self):
        """Genera una playlist aleatoria de los candidatos disponibles"""
        # Si hay menos candidatos que el tamaño deseado, devolvemos lo que hay
        if len(self.candidates) <= self.playlist_size:
            return self.candidates
        return random.sample(self.candidates, self.playlist_size)

    def fitness(self, playlist: List[Dict]) -> float:
        """
        Calcula qué tan buena es la playlist.
        Criterio: El PROMEDIO del cromosoma de la playlist debe parecerse al TARGET.
        """
        # Extraemos los cromosomas de las canciones en la playlist actual
        matrix = np.array([p['cromosoma'] for p in playlist])
        
        # Promediamos para obtener el "Vibe General" de esta playlist
        playlist_avg_vibe = np.mean(matrix, axis=0)
        
        # Calculamos similitud con la canción objetivo
        score = self.cosine_similarity(playlist_avg_vibe, self.target)
        
        return score

    def mutate(self, playlist: List[Dict]):
        """Intercambia una canción de la playlist por otra del pool de candidatos"""
        if random.random() < 0.2: # 20% de probabilidad de mutar
            idx_out = random.randint(0, len(playlist) - 1)
            new_track = random.choice(self.candidates)
            
            # Evitar duplicados simples (opcional, pero recomendado)
            ids_actuales = [t['id'] for t in playlist]
            if new_track['id'] not in ids_actuales:
                playlist[idx_out] = new_track
                
        return playlist

    def crossover(self, parent1, parent2):
        """Mezcla dos playlists"""
        # Protegemos el crossover si la lista es muy pequeña (ej. 1 canción)
        if len(parent1) < 2:
            return parent1

        split = random.randint(1, len(parent1) - 1)
        child = parent1[:split] + parent2[split:]
        
        # Corte simple: si quedó más larga o corta, ajustamos
        return child[:self.playlist_size]

    def run(self):
        # Si no hay suficientes canciones, regresamos las que haya
        if len(self.candidates) < self.playlist_size:
            print(f"⚠️ Advertencia: Pocos candidatos ({len(self.candidates)}) para el target ({self.playlist_size}). Devolviendo todos.")
            return self.candidates

        # 1. Población Inicial
        population = [self.create_individual() for _ in range(self.population_size)]

        best_global = None
        best_score = -1

        for _ in range(self.generations):
            # 2. Evaluar
            population = sorted(population, key=self.fitness, reverse=True)
            
            current_best = population[0]
            current_score = self.fitness(current_best)
            
            if current_score > best_score:
                best_score = current_score
                best_global = current_best

            # Si encontramos una similitud > 98%, paramos (optimización)
            if best_score > 0.98:
                break

            # 3. Selección (Top 50%)
            survivors = population[:self.population_size // 2]
            
            # 4. Reproducción
            next_gen = survivors[:]
            while len(next_gen) < self.population_size:
                p1, p2 = random.sample(survivors, 2)
                child = self.crossover(p1, p2)
                child = self.mutate(child)
                next_gen.append(child)
            
            population = next_gen

        return best_global