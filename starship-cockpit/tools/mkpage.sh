page () 
{ 
    cat > $1 <<EOF
<!doctype html><html><head><meta charset="utf-8"><title>$2</title>
<style>html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:transparent}canvas{display:block}</style></head>
<body><canvas id="c" width="1920" height="1080"></canvas>
<script>$3</script><script src="ship.js"></script><script src="$4"></script></body></html>
EOF

}
