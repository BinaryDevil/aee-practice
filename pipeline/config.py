import re

PROMO_PATTERNS = [r'all\s*ears\s*english', r'allersenglish', r'(?:fluency|english)\s+(?:score|quiz)', r'download(?:ed|s)?\s+(?:more than|over|\d)', r'\b(?:dot com|slash|subscribe|sponsor(?:ed)?|free trial)\b', r'\b(?:our|the|this)\s+(?:course|app|newsletter|website)\b', r'\b(?:go to|visit)\s+\S+\s*(?:\.com|dot com)', r'\b(?:million times|follow button)\b']
PROMO = re.compile('|'.join(PROMO_PATTERNS), re.I)
CUE = re.compile(r'\b(?:means?|meaning|idiom|phrasal verb|expression|phrase|slang|for example|number (?:one|two|three|four|five)|the (?:first|next|last) one|another|adjective)\b', re.I)
IDIO = {'idiomatic','slang','informal','colloquial','figuratively'}
PLACE = {'someone','something','somebody',"one's",'oneself',"someone's"}
STOP = set('you know|i mean|of course|kind of|sort of|a lot|right now|i think|for sure|at all|thank you|you guys|go to|a little|so far|look at|talk about|come on|by the way|in fact|as well|such as|all right|let me|i guess|no way|to be|let us|let us see|let\'s see|this way|figure out|stand up|right stuff|good guy|you think|need to|keep up|use it|want to|there be'.split('|'))
FUNC = set('i you he she it we they be do have say would will can could should a an the of to in on at for with and or but that this there so as like just not all one see know want feel good get go make take use thing way right stuff guy'.split())
META = set('vocabulary idiom phrasal verb adjective adverb noun slang slangy podcast quiz episode subscribe awesome listener english word phrase expression example speaker commentator participle syllable pronounce pronunciation intonation dialect grammar linguistic'.split())
# Words too weak to make a phrase a learnable item on their own ("do what", "so what", "come to").
WEAK = set('what who how why when where which then now here there is are was were said says come came coming up out off back over around down into about from by me him her them us my your'.split())
