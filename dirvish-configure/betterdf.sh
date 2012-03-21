#!/bin/bash

df -Ph | \
awk ' 
{ 
    sub(/\/dev\/mapper\/dataVG-/,"") 
} 
/backups|Filesystem/ {
    printf "%-35s %-6s %-6s %-6s", $1, $2, $3, $4; 
    if ($5 > 90 && $5 != "Use%") 
        printf "\033[1;31m%-5s\033[0m\n", $5;
    else if ($5 > 80 && $5 != "Use%") 
        printf "\033[1;33m%-5s\033[0m\n", $5;
    else 
        printf "%-5s\n", $5;
} ' | \
sort
