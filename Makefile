.PHONY: verify

verify:
	python -m pip install -e .[dev]
	pytest -q
	python -m sim --scenario flag --seed 42 --rate 1000 &
	sleep 0.5
	python -c "$$(cat tests/_smoke_client.py)"
	pkill -f 'python -m sim'
