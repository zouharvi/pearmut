# sets up a local VM that runs pearmut and tunnels it through ngrok

sudo snap install multipass
multipass launch --name pearmut-box
multipass mount ~/pearmut/data_vm/ pearmut-box:/home/ubuntu/data_vm
multipass shell pearmut-box

sudo apt update
sudo apt install python3-pip -y
python3 -m pip config set global.break-system-packages true
pip install pearmut
export PATH=$PATH:/home/ubuntu/.local/bin
sudo snap install ngrok
ngrok authtoken YOUR_NGROK_AUTH_TOKEN_HERE

nohup ngrok http 8001 --url=pearmut.ngrok.io --traffic-policy-file=misc/policy.yml 1>ngrok.out 2>ngrok.err &
nohup pearmut run --port 8001 --url https://pearmut.ngrok.io 1>pearmut.out 2>pearmut.err &

ngrok http 8001 --url=pearmut.ngrok.io --traffic-policy-file=misc/policy.yml
pearmut run --port 8001 --url https://pearmut.ngrok.io