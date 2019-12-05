for i in `seq 1 10`; do
    for ip in `seq 1 4`; do
        curl -d "entry=Loop this msg times: ${i} from server: ${ip}" -X 'POST' "http://10.1.0.${ip}:80/board" &
    done
done