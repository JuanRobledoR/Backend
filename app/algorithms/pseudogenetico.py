import numpy as np
import random
from typing import List, Dict

class GeneticOptimizer:
    # Configura el optimizador ligero con los candidatos disponibles y el cromosoma objetivo.
    def __init__(self, population_data: List[Dict], target_chromosome: List[float], target_size: int = 5):
        self.candidates = population_data
        self.target = np.array(target_chromosome)
        self.playlist_size = target_size   
        self.population_size = 20 
        self.generations = 50     
        
        self.max_vals = np.array([
            200.0,   
            5000.0,  
            1.0,     
            *[200.0]*13 
        ])

    # Escala los valores del vector entre 0 y 1 aprox. para evitar sesgos por magnitud.
    def normalize(self, vector):
        v = np.array(vector)
        return v / (self.max_vals + 1e-6)

    # Calcula la similitud coseno entre dos vectores normalizados (1.0 = idénticos).
    def cosine_similarity(self, vec_a, vec_b):
        a_norm = self.normalize(vec_a)
        b_norm = self.normalize(vec_b)
        
        dot = np.dot(a_norm, b_norm)
        norm_a = np.linalg.norm(a_norm)
        norm_b = np.linalg.norm(b_norm)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # Crea una playlist inicial seleccionando canciones al azar de los candidatos.
    def create_individual(self):
        if len(self.candidates) <= self.playlist_size:
            return self.candidates
        return random.sample(self.candidates, self.playlist_size)

    # Evalúa la playlist calculando qué tan cerca está su promedio del objetivo (Cosine Similarity).
    def fitness(self, playlist: List[Dict]) -> float:
        matrix = np.array([p['cromosoma'] for p in playlist])
        playlist_avg_vibe = np.mean(matrix, axis=0)
        score = self.cosine_similarity(playlist_avg_vibe, self.target)
        return score

    # Introduce variabilidad reemplazando aleatoriamente una canción por otra del pool general.
    def mutate(self, playlist: List[Dict]):
        if random.random() < 0.2: 
            idx_out = random.randint(0, len(playlist) - 1)
            new_track = random.choice(self.candidates)
            
            ids_actuales = [t['id'] for t in playlist]
            if new_track['id'] not in ids_actuales:
                playlist[idx_out] = new_track
                
        return playlist

    # Combina dos playlists padre cortándolas en un punto aleatorio para crear un hijo.
    def crossover(self, parent1, parent2):
        if len(parent1) < 2:
            return parent1

        split = random.randint(1, len(parent1) - 1)
        child = parent1[:split] + parent2[split:]
        return child[:self.playlist_size]

    # Ejecuta el bucle de optimización genética simple para refinar la playlist final.
    def run(self):
        if len(self.candidates) < self.playlist_size:
            print(f"⚠️ Advertencia: Pocos candidatos ({len(self.candidates)}) para el target ({self.playlist_size}). Devolviendo todos.")
            return self.candidates

        population = [self.create_individual() for _ in range(self.population_size)]

        best_global = None
        best_score = -1

        for _ in range(self.generations):
            population = sorted(population, key=self.fitness, reverse=True)
            
            current_best = population[0]
            current_score = self.fitness(current_best)
            
            if current_score > best_score:
                best_score = current_score
                best_global = current_best

            if best_score > 0.98:
                break

            survivors = population[:self.population_size // 2]
            
            next_gen = survivors[:]
            while len(next_gen) < self.population_size:
                p1, p2 = random.sample(survivors, 2)
                child = self.crossover(p1, p2)
                child = self.mutate(child)
                next_gen.append(child)
            
            population = next_gen

        return best_global