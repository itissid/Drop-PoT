I had to change my source tree to src/ layout based on some errors in using drop_backend in projects: 
https://stackoverflow.com/questions/50155464/using-pytest-with-a-src-layer

It just makes life easier. See justifications https://blog.ionelmc.ro/2014/05/25/python-packaging/

Tests can be run from the project directory(~/workspace/drop) itself: 
python  -m pytest  --capture=tee-sys  tests/integration/
python  -m pytest  --capture=tee-sys  tests/unit/

Pylint complained about not finding imports because it did not have context 
