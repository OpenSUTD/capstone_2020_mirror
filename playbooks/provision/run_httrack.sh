# -s0 : Never follow robots.txt
# -c16 : 16 parallel connections (no effect, limits to 8)
# -T300 : Request timeouts after 300 seconds
# -R5 : 5 retries
# -H0 : host is never abandoned
# -%P0 : don't use extended parsing
# -t : test all URLs
# -o0 : don't generate 404
# -X : purge old files after update
# -b1 : accept cookies
# -q : no questions
# -I : make an index
# -i : continue an interrupted mirror using the cache
# -f : log in files
httrack "https://{{httrack_target}}" -O "/var/mirror" "+*{{httrack_target}}/*" -s0 -c16 -T300 -R5 -H0 -%P0 -t -o0 -X -b1 -q -I -i -f
chown -R ec2-user:ec2-user /var/mirror