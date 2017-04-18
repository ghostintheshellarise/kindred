
from kindred import *
import xml.etree.ElementTree
import sys

from kindred import CandidateBuilder


class Entity:
	def __init__(self,entityType,entityID,text,pos):
		posErrorMsg = "Entity position must be list of tuples (startPos,endPos)"
	
		assert isinstance(entityType,str)
		assert isinstance(entityID,int)
		assert isinstance(text,str)
		assert isinstance(pos,list), posErrorMsg
		for p in pos:
			assert isinstance(p,tuple), posErrorMsg
			assert len(p) == 2, posErrorMsg
			assert isinstance(p[0],int), posErrorMsg
			assert isinstance(p[1],int), posErrorMsg
	
		self.entityType = entityType
		self.entityID = entityID
		self.text = text
		self.pos = pos
		
	def __str__(self):
		out = "%s:'%s' id=%d %s" % (self.entityType,self.text,self.entityID,str(self.pos))
		return out
		
	def __repr__(self):
		return self.__str__()
		
	def __eq__(self, other):
		"""Override the default Equals behavior"""
		if isinstance(other, self.__class__):
			return self.__dict__ == other.__dict__
		return False
	
	def __ne__(self, other):
		"""Define a non-equality test"""
		return not self.__eq__(other)


class TextAndEntityData:
	def __init__(self,text):
		#doc = "<doc>%s</doc>" % text
		#e = xml.etree.ElementTree.fromstring(doc)
		#for child in e:
		#	print child, child.text
		#for child in e.itertext():
		#	print child,type(child)
		#print(dir(e))
		#print e, e.text
		text = text.replace('>','<')
		split = text.split('<')
		
		tagStyle = None
		isTag = False
		currentText = ""
		openTags = {}
		minID = 1
		
		preEntities = {}
		for section in split:
			if isTag:
				tagSplit = section.split(' ')
				assert len(tagSplit) == 1 or len(tagSplit) == 2
				if len(tagSplit) == 1:
					if section.startswith('/'): # close a tag
						entityType = section[1:]
						assert entityType in openTags, "Trying to close a non-existent %s element" % entityType
						
						entityStart,entityID = openTags[entityType]
						entityEnd = len(currentText)
						entityText = currentText[entityStart:]
						#entity = Entity(entityType,entityID,entityText,pos=[(entityStart,entityEnd)])
						#entities.append(entity)
						key = (entityType,entityID)
						if key in preEntities:
							preEntities[key]['text'] += ' ' + entityText
							preEntities[key]['pos'].append((entityStart,entityEnd))
						else:
							preEntities[key] = {}
							preEntities[key]['text'] = entityText
							preEntities[key]['pos'] = [(entityStart,entityEnd)]
						
						
						del openTags[entityType]
					else: # open a tag
						assert tagStyle != 2, "Cannot mix entity tags with and without IDs"
						tagStyle = 1
					
						entityType = section
						openTags[entityType] = (len(currentText),minID)
						minID += 1
				elif len(tagSplit) == 2:
					assert tagStyle != 1, "Cannot mix entity tags with and without IDs"
					tagStyle = 2
						
					entityType,idinfo = tagSplit
					assert idinfo.startswith('id=')
					idinfoSplit = idinfo.split('=')
					assert len(idinfoSplit) == 2
					entityID = int(idinfoSplit[1])
					
					openTags[entityType] = (len(currentText),entityID)
			else:
				currentText += section
				
			# Flip each iteration
			isTag = not isTag
			
		assert len(openTags) == 0, "All tags were not closed in %s" % text
		
		entities = []
		for (entityType,entityID),entityInfo in preEntities.iteritems():
			entity = Entity(entityType,entityID,entityInfo['text'],entityInfo['pos'])
			entities.append(entity)
		
		self.text = currentText
		self.entities = entities
		
	def getEntities(self):
		return self.entities
		
	def getText(self):
		return self.text
		
class RelationData:
	def __init__(self,text,relations):
		relationErrorMsg = "Relation must be a list of triples of ('relationType',entityID1,entityID2)"
		assert isinstance(relations,list), relationErrorMsg
		for r in relations:
			assert isinstance(r,tuple), relationErrorMsg
			assert len(r) == 3, relationErrorMsg
			assert isinstance(r[0],basestring), relationErrorMsg
			assert isinstance(r[1],int), relationErrorMsg
			assert isinstance(r[2],int), relationErrorMsg
		
		self.textAndEntityData = TextAndEntityData(text)
		self.relations = relations
		
	def getEntities(self):
		return self.textAndEntityData.getEntities()
		
	def getText(self):
		return self.textAndEntityData.getText()
		
	def getTextAndEntities(self):
		return self.textAndEntityData
		
	def getRelations(self):
		return self.relations
	
class CandidateRelation:
	def __init__(self,processedSentence,entitiesInRelation):
		assert isinstance(processedSentence,ProcessedSentence)
		assert isinstance(entitiesInRelation,tuple)
		assert len(entitiesInRelation) > 1
		
		entitiesInSentence = processedSentence.getEntityIDs()
		
		for entityID in entitiesInRelation:
			assert entityID in entitiesInSentence, "All entities in candidate relation should actually be in the associated sentence"
			
		self.processedSentence = processedSentence
		self.entitiesInRelation = entitiesInRelation
		
	def __str__(self):
		return str((self.processedSentence.__str__(),self.entitiesInRelation))
		
	def __repr__(self):
		return self.__str__()
		
	
class Token:
	def __init__(self,word,lemma,partofspeech,startPos,endPos):
		self.word = word
		self.lemma = lemma
		self.partofspeech = partofspeech
		self.startPos = startPos
		self.endPos = endPos

	def __str__(self):
		return self.word
		
	def __repr__(self):
		return self.__str__()

class ProcessedSentence:
	# TODO: Camelcase consistency in this class

	def printDependencyGraph(self):
		print "digraph sentence {"
		used = set()
		for a,b,_ in self.dependencies:
			used.update([a,b])
			aTxt = "ROOT" if a == -1 else str(a)
			bTxt = "ROOT" if b == -1 else str(b)

			print "%s -> %s;" % (aTxt,bTxt)

		for i,token in enumerate(self.tokens):
			if i in used:
				print "%d [label=\"%s\"];" % (i,token.word)
		print "}"
		
	def __str__(self):
		tokenWords = [ t.word for t in self.tokens ]
		return " ".join(tokenWords)

	def getEdgeTypes(self,edges):
		types = [ t for a,b,t in self.dependencies if (a,b) in edges or (b,a) in edges ]
		return types

	def extractSubgraphToRoot(self,minSet):
		neighbours = defaultdict(list)
		for a,b,_ in self.dependencies:
			neighbours[b].append(a)
			
		toProcess = list(minSet)
		alreadyProcessed = []
		edges = []
		while len(toProcess) > 0:
			thisOne = toProcess[0]
			toProcess = toProcess[1:]
			alreadyProcessed.append(thisOne)
			for a in neighbours[thisOne]:
				if not a in alreadyProcessed:
					toProcess.append(a)
					edges.append((a,thisOne))
		return alreadyProcessed,edges
		
	def extractMinSubgraphContainingNodes(self, minSet):
		import networkx as nx
		
		assert isinstance(minSet, list)
		for i in minSet:
			assert isinstance(i, int)
			assert i >= 0
			assert i < len(self.tokens)
		G1 = nx.Graph()
		for a,b,_ in self.dependencies:
			G1.add_edge(a,b)

		G2 = nx.Graph()
		paths = {}

		minSet = sorted(list(set(minSet)))
		setCount1 = len(minSet)
		minSet = [ a for a in minSet if G1.has_node(a) ]
		setCount2 = len(minSet)
		if setCount1 != setCount2:
			print "WARNING. %d node(s) not found in dependency graph!" % (setCount1-setCount2)
		for a,b in itertools.combinations(minSet,2):
			try:
				path = nx.shortest_path(G1,a,b)
				paths[(a,b)] = path
				G2.add_edge(a,b,weight=len(path))
			except nx.exception.NetworkXNoPath:
				print "WARNING. No path found between nodes %d and %d!" % (a,b)
			
		# TODO: This may throw an error if G2 ends up having multiple components. Catch it gracefully.
		minTree = nx.minimum_spanning_tree(G2)
		nodes = set()
		allEdges = set()
		for a,b in minTree.edges():
			path = paths[(min(a,b),max(a,b))]
			for i in range(len(path)-1):
				a,b = path[i],path[i+1]
				edge = (min(a,b),max(a,b))
				allEdges.add(edge)
			nodes.update(path)

		return nodes,allEdges
	
	def buildDependencyInfo(self):
		self.dep_neighbours = defaultdict(set)
		for (a,b,type) in self.dependencies:
			self.dep_neighbours[a].add(b)
			self.dep_neighbours[b].add(a)
		self.dep_neighbours2 = defaultdict(set)
		for i in self.dep_neighbours:
			for j in self.dep_neighbours[i]:
				self.dep_neighbours2[i].update(self.dep_neighbours[j])
			self.dep_neighbours2[i].discard(i)
			for j in self.dep_neighbours[i]:
				self.dep_neighbours2[i].discard(j)
		
	def invertTriggers(self):
		self.locsToTriggerIDs = {}
		self.locsToTriggerTypes = {}
		for triggerid,locs in self.entityLocs.iteritems():
			type = self.entityTypes[triggerid]
			self.locsToTriggerIDs[tuple(locs)] = triggerid
			self.locsToTriggerTypes[tuple(locs)] = type

	def getEntityIDs(self):
		return self.entityLocs.keys()
			
	def __init__(self, tokens, dependencies, entityLocs, entityTypes, relations=[]):
		assert isinstance(tokens, list) 
		assert isinstance(dependencies, list) 
		assert isinstance(entityLocs, dict) 
		assert isinstance(entityTypes, dict)
		
		assert len(entityLocs) == len(entityTypes)
		
		self.tokens = tokens
		self.entityLocs = entityLocs
		self.entityTypes = entityTypes
		self.dependencies = dependencies
		
		entitiesInSentence = self.getEntityIDs()
		for r in relations:
			relationEntityIDs = r[1:]
			for relationEntityID in relationEntityIDs:
				assert relationEntityID in entitiesInSentence, "Relation cannot contain entity not in this sentence"
		
		self.relations = relations
	
		self.invertTriggers()

