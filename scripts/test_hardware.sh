
while  true
do
    echo 'Start test'
    date
    echo '++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++'
    curl -sIXGET https://github.com
    echo '++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++'
    echo 'End test'
    sleep 60
done