install:
	python setup.py install &> /dev/null
	make clean

debug-install:
	python setup.py install
	make clean

test:
	pytest -p no:warnings --tb=short
	make clean

clean:
	find . | grep -E "(__pycache__|\.pyc|\.pyo|.coverage|.DS_Store$$)" | xargs rm -rf
