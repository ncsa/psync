/^\(<FSItem/{s=index($0,"/mnt/a"); e=index($0,">, <FSItem "); l=e-s; printf("%s\n",substr($0,s,l))}
