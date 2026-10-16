import json
import os
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger("UserBot.ML")

class PreferenceEngine:
    def __init__(self, data_dir="data", filename="card_preferences.json"):
        os.makedirs(data_dir, exist_ok=True)
        self.storage_path = os.path.join(data_dir, filename)
        
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b")
        self.model = LogisticRegression(class_weight="balanced")
        self.dataset = self._load_data()
        self.is_trained = False
        
        self._retrain()

    def _load_data(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded [bold cyan]{len(data)}[/] ML training pairs from disk.")
                    return data
            except Exception as e:
                logger.error(f"Failed to load preference data: {e}")
                return []
        logger.info("No existing preference data found. Starting fresh ML dataset.")
        return []

    def _save_data(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.dataset, f, indent=2)
            logger.debug("Preference data saved to disk.")
        except Exception as e:
            logger.error(f"Failed to save preference data: {e}")

    def record_interaction(self, chosen_card: dict, rejected_cards: list[dict]):
        for rejected in rejected_cards:
            self.dataset.append({
                "preferred": f"{chosen_card['character']} {chosen_card['series']}",
                "rejected": f"{rejected['character']} {rejected['series']}"
            })
        self._save_data()
        self._retrain()

    def _retrain(self):
        if len(self.dataset) < 2:
            self.is_trained = False
            logger.debug("Not enough data to train ML model (requires at least 2 interactions).")
            return

        texts = []
        labels = []
        for pair in self.dataset:
            texts.extend([pair["preferred"], pair["rejected"]])
            labels.extend([1, 0])

        try:
            X = self.vectorizer.fit_transform(texts)
            self.model.fit(X, labels)
            self.is_trained = True
            logger.info("[bold cyan]ML Preference Engine[/] successfully trained.")
        except Exception as e:
            self.is_trained = False
            logger.error(f"Model retraining failed: {e}")

    def rank_cards(self, cards: list[dict]):
        """Returns the recommended slot and a list of confidence scores."""
        if not self.is_trained:
            logger.debug("Model untrained; returning default equal predictions.")
            return 1, [1.0 / len(cards)] * len(cards)

        texts = [f"{c['character']} {c['series']}" for c in cards]

        try:
            X = self.vectorizer.transform(texts)
            probs = self.model.predict_proba(X)[:, 1]
            scores = [float(p) for p in probs]
            
            best_idx = int(np.argmax(scores))
            recommendation = best_idx + 1
            
            log_str = " vs ".join([f"Slot {i+1} ({s:.2f})" for i, s in enumerate(scores)])
            logger.info(f"[cyan]AI Prediction:[/] {log_str} -> Recommending [bold]Slot {recommendation}[/]")
            return recommendation, scores
        except Exception as e:
            logger.error(f"Prediction failed, falling back to default: {e}")
            return 1, [1.0 / len(cards)] * len(cards)