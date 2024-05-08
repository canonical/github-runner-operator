
while  true
do
    echo 'Start tests'
    echo 'Disk'
    df -h
    echo 'Memory'
    free -h
    echo 'Network'
    curl -sIXGET https://github.com
    echo 'End tests'
    sleep 60
done