import os
import tkinter as tk
from tkinter import filedialog, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading
import queue
import platform
from pathlib import Path

class DirectoryAnalyzer(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Analyseur de Répertoire")
        self.geometry("800x600")

        # Frame principale
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Bouton pour sélectionner le répertoire
        self.select_button = ttk.Button(
            self.main_frame, 
            text="Sélectionner un répertoire",
            command=self.select_directory
        )
        self.select_button.pack(pady=10)

        # Frame pour les informations de progression
        self.progress_frame = ttk.Frame(self.main_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)

        # Barre de progression avec pourcentage
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Label pour le pourcentage
        self.percent_label = ttk.Label(self.progress_frame, text="0%")
        self.percent_label.pack(side=tk.RIGHT)

        # Labels pour les détails
        self.details_frame = ttk.Frame(self.main_frame)
        self.details_frame.pack(fill=tk.X, pady=5)

        self.files_count_label = ttk.Label(self.details_frame, text="Fichiers analysés: 0")
        self.files_count_label.pack(side=tk.LEFT, padx=5)

        self.current_folder_label = ttk.Label(self.details_frame, text="")
        self.current_folder_label.pack(side=tk.LEFT, padx=5)

        # Frame pour les graphiques
        self.graph_frame = ttk.Frame(self.main_frame)
        self.graph_frame.pack(fill=tk.BOTH, expand=True)

        # Liste des dossiers
        self.tree = ttk.Treeview(
            self.main_frame, 
            columns=("Taille", "Pourcentage"),
            show="headings"
        )
        self.tree.heading("Taille", text="Taille (MB)")
        self.tree.heading("Pourcentage", text="% du Total")
        self.tree.pack(pady=10, fill=tk.BOTH, expand=True)

        # Queue pour la communication entre threads
        self.queue = queue.Queue()
        
    def update_progress(self, value, files_count, current_folder):
        """Met à jour la barre de progression et les informations"""
        self.progress_var.set(value)
        self.percent_label.config(text=f"{value:.1f}%")
        self.files_count_label.config(text=f"Fichiers analysés: {files_count}")
        self.current_folder_label.config(text=f"Dossier en cours: {current_folder}")
        self.update_idletasks()

    def count_items(self, path):
        """Compte le nombre total de fichiers à analyser"""
        total_files = 0
        try:
            for root, dirs, files in os.walk(path, followlinks=False):
                total_files += len(files)
        except Exception:
            pass
        return max(total_files, 1)  # Éviter la division par zéro

    def get_directory_size(self, path, total_files, processed_files, queue_ref):
        """Calcule la taille d'un répertoire avec suivi de la progression"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
                for filename in filenames:
                    try:
                        file_path = os.path.join(dirpath, filename)
                        if os.path.exists(file_path) and not os.path.islink(file_path):
                            total_size += os.path.getsize(file_path)
                            processed_files[0] += 1
                            progress = (processed_files[0] / total_files) * 100
                            queue_ref.put(("progress", progress, processed_files[0], os.path.basename(dirpath)))
                    except (OSError, PermissionError):
                        processed_files[0] += 1
                        continue
        except (OSError, PermissionError):
            pass
        return total_size

    def analyze_directory_thread(self, path):
        """Fonction exécutée dans un thread séparé pour l'analyse"""
        try:
            # Compter le nombre total de fichiers
            self.queue.put(("progress", 0, 0, "Comptage des fichiers..."))
            total_files = self.count_items(path)
            processed_files = [0]  # Liste mutable pour le compteur

            # Analyser les dossiers
            subdirs = {}
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    size = self.get_directory_size(item_path, total_files, processed_files, self.queue)
                    subdirs[item] = size

            # Calculer la taille totale
            total_size = sum(subdirs.values())
            
            # Trier les résultats
            sorted_dirs = dict(sorted(subdirs.items(), key=lambda x: x[1], reverse=True))
            
            self.queue.put(("result", sorted_dirs, total_size))
            self.queue.put(("progress", 100, processed_files[0], "Analyse terminée"))

        except Exception as e:
            self.queue.put(("error", str(e)))

    def check_queue(self):
        """Vérifie la queue pour les mises à jour du thread"""
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg[0] == "progress":
                    self.update_progress(msg[1], msg[2], msg[3])
                elif msg[0] == "result":
                    self.update_graphs(msg[1], msg[2])
                elif msg[0] == "error":
                    self.current_folder_label.config(text=f"Erreur: {msg[1]}")
                    self.select_button.config(state="normal")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.check_queue)

    def update_graphs(self, sorted_subdirs, total_size):
        """Met à jour les graphiques et la liste"""
        # Nettoyer l'affichage précédent
        self.tree.delete(*self.tree.get_children())
        for widget in self.graph_frame.winfo_children():
            widget.destroy()

        # Créer la figure avec deux sous-graphiques
        fig = Figure(figsize=(10, 4))
        
        # Sélectionner les 5 plus grands dossiers
        top_5_dirs = dict(list(sorted_subdirs.items())[:5])
        
        # Camembert
        ax1 = fig.add_subplot(121)
        sizes = list(top_5_dirs.values())
        labels = list(top_5_dirs.keys())
        ax1.pie(sizes, labels=labels, autopct='%1.1f%%')
        ax1.set_title("Top 5 des dossiers les plus lourds")

        # Graphique en barres
        ax2 = fig.add_subplot(122)
        x = range(len(sizes))
        ax2.bar(x, [s/1024/1024 for s in sizes])  # Convertir en MB
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=45)
        ax2.set_title("Comparaison des tailles (MB)")
        ax2.set_ylabel("Taille (MB)")

        # Ajuster la mise en page
        fig.tight_layout()

        # Ajouter les graphiques à l'interface
        canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Mettre à jour la liste des dossiers
        for name, size in sorted_subdirs.items():
            size_mb = size / (1024 * 1024)  # Convertir en MB
            percentage = (size / total_size) * 100 if total_size > 0 else 0
            self.tree.insert("", tk.END, values=(f"{size_mb:.2f}", f"{percentage:.2f}"))

        self.select_button.config(state="normal")

    def select_directory(self):
        """Gère la sélection du répertoire et lance l'analyse"""
        directory = filedialog.askdirectory()
        if directory:
            # Désactiver le bouton pendant l'analyse
            self.select_button.config(state="disabled")
            
            # Réinitialiser les indicateurs
            self.progress_var.set(0)
            self.percent_label.config(text="0%")
            self.files_count_label.config(text="Fichiers analysés: 0")
            self.current_folder_label.config(text="Démarrage de l'analyse...")
            
            # Lancer l'analyse dans un thread séparé
            analysis_thread = threading.Thread(
                target=self.analyze_directory_thread,
                args=(directory,),
                daemon=True
            )
            analysis_thread.start()
            
            # Démarrer la vérification de la queue
            self.check_queue()

if __name__ == "__main__":
    app = DirectoryAnalyzer()
    app.mainloop()