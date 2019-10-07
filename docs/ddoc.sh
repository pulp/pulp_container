source ~/.bashrc
prestart
cd ~/devel/pulp_container/docs/
sleep 2
make clean
make html
cd ~/devel/pulp_container/docs/_build/html
python2 -m SimpleHTTPServer 1234
