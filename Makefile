.PHONY: scrape features explore train train-all simulate evaluate pipeline test clean

# Coleta dados de todas as fontes habilitadas
scrape:
	python cli/scrape.py --config configs/data.yaml

# Gera features processadas a partir de data/raw/
features:
	python cli/features.py --config configs/data.yaml

# Roda analise exploratoria (Fase 3)
explore:
	python cli/explore.py

# Treina um modelo especifico (Fase 4). Uso: make train MODEL=dixon_coles
train:
	python cli/train.py --model $(MODEL) --config configs/models.yaml

# Treina todos os modelos em sequencia (Fase 4)
train-all:
	python cli/train.py --model poisson      --config configs/models.yaml
	python cli/train.py --model dixon_coles  --config configs/models.yaml
	python cli/train.py --model logistic     --config configs/models.yaml
	python cli/train.py --model bayesian     --config configs/models.yaml

# Simula a Copa 2026 (Fase 5). Uso: make simulate N=50000
simulate:
	python cli/simulate.py --config configs/simulation.yaml --n-simulations $(or $(N),50000)

# Avalia e compara modelos (Fase 6)
evaluate:
	python cli/evaluate.py

# Roda o pipeline DVC completo
pipeline:
	dvc repro

# Roda os testes
test:
	pytest -q

# Remove outputs intermediarios
clean:
	rm -rf outputs/ mlruns/ __pycache__/
