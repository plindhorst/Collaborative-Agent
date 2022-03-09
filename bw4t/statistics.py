from typing import final, List, Dict, Final
import sys
import csv
import os

MOVES=['MoveNorth','MoveNorthEast','MoveEast','MoveSouthEast',
       'MoveSouth','MoveSouthWest','MoveWest','MoveNorthWest']

class Statistics:
    def __init__(self, filename:str):
        '''
        @param filename the path to the csv file to read.
        It  is assumed that first row of the file contains the element headers
        and these are used as dict keys.
        header is assumed to have keys like 
        done;agent1_344_msgs;agent1_344_drops;agent2_345_msgs;
        agent2_345_drops;human1_346_msgs;human1_346_drops;
        agent1_344_acts;agent2_345_acts;human1_346_acts;world_nr;tick_nr

        done is True only in the last row.
        drops contains number of drops IN DROP ZONE.
        '''
        self._filename=filename
        self._contents=self._read()
        self._analyse()
        
    def _read(self)->List[Dict[str,str]]:
        '''
        read contents from csv file
        @return it as list of dictionaries, one dictionary for each row.
        It  is assumed that first row of the file contains the element headers
        and these are used as dict keys.
        The dict for each row contains the keys which are the element headers,
        and the values which is the value in the column of that header
        eg if file has header "name","id" and a row "jan,12" then the dict
        for that row will be {'name':jan, 'id':12}.
        '''
        header:List[str]=[]
        contents:List[Dict[str,str]]=[]
        with open(self._filename) as csvfile:
            reader = csv.reader(csvfile, delimiter=';', quotechar="'")
            for row in reader:
                if header==[]:
                    header=row
                    continue
                res = {header[i]: row[i] for i in range(len(header))} 
                contents.append(res)
        return contents

    def _analyse(self):
        '''
        analyse the performance log dictionary contained in _contents.
        Dict is assumed to have keys like 
        done;agent1_344_msgs;agent1_344_drops;agent2_345_msgs;
        agent2_345_drops;human1_346_msgs;human1_346_drops;
        agent1_344_acts;agent2_345_acts;human1_346_acts;world_nr;tick_nr
 
        '''
        agents=self.getAgents()
        self._moves={agent:0 for agent in agents}
        self._messages={agent:0 for agent in agents}
        self._drops={agent:0 for agent in agents}
        for row in self._contents:
            for agent in agents:
                if row[agent+'_acts']  in MOVES:
                    self._moves[agent] += 1
                if 'DropObject'==row[agent+'_acts']:
                    self._drops[agent]+=1
                self._messages[agent] = row[agent+'_mssg']
                
    def getLastTick(self):
        '''
        @return tick nr of last line
        '''
        return self._contents[-1]['tick_nr']        
    
    def isSucces(self):
        '''
        return 'done' field of last row 
        '''
        return self._contents[len(self._contents)-1]['done']
    
    def getAgents(self):
        '''
        @return list of agents in the contents
        '''
        if len(self._contents)==0:
            return []
        agents =[]
        for header in self._contents[0].keys():
            if header.endswith("_acts"):
                agents.append(header[:len(header)-5])
        return agents
                
    
    def __str__(self):
        return "Statistics for "+self._filename\
            +"\nagents:"+str(self.getAgents())\
            +"\nsuccess:"+str(self.isSucces())\
            +"\nmessages:"+str(self._messages)\
            +"\ndrops:"+str(self._drops)\
            +"\nmoves:"+str(self._moves)\
            +"\ntotal moves:"+str(sum(self._moves.values()))\
            +"\nlast tick:"+str(self.getLastTick())
        
if __name__ == "__main__":
    if len(sys.argv)!=2:
        raise ValueError("usage: "+sys.argv[0]+" <filename>")
    print (os.getcwd())
    print(Statistics(sys.argv[1]))
    
    