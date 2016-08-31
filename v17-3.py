"""Inserts cohesive elements into a defined damage zone in bone.

This program takes an "inp" Abaqus file containing bone material and a defined damage zone
and inserts cohesive elements within the damage region. An "inp" file is then output with the
new cohesive element zone defined.

Example:
	Given document file with the name "input.inp" located in the folder "inp/input.inp", 
	change the inputName = "input" and run the python program from the command window.

		$ python v17-3.py
	
	Output will be found in "reports/<output file name>" in the directory where this program
	is run.
	
For more information on how to use this program, please refer to README.md and the SOP packaged
with this program.

This program has been tested to run on WINDOWS and UNIX based systems, although will run best on
UNIX based systems due to the use of the multiprocessing module to perform parrallel computing.

Due to the nature of how WINDOWS handles passing objects to proceses, using more processes may in 
fact be slower than using less due to limitations in the WINDOWS process architecture. A reasonable
number of cores to use on WINDOWS could be (maximum number of cores)/2.

"""

"""Main function/starting script of the program.

Args:
	inputName (str): String variable containing input inp file name found in the "inp" directory
	core (int): Defines the number of cpu cores to be used when running this program. This program
		utilizes the multiprocessing to speed up computation.
	cohesiveElementStartNumber (int): Starting number for cohesive elements to be inserted to start
		counting at. This number should be larger than the total number of elements defined in the
		input inp file.
	cohesiveNodeStartNumber (int): Starting number for cohesive nodes to be inserted to start
		counting at. This number should be larger than the total number of nodes defined in the
		input inp file.
	nodeStartInp (optional)(str): Start of the line in input inp file that indicates the start of the node 
		section of the file.
	nodeEndInp (optional)(str): Start of the line in input inp file that indicates the end of the node 
		section of the file.
	elementNormalStartInp (optional)(str): Start of the line in input inp file that indicates the start of the element 
		section of the file.
	elementNormalEndInp (optional)(str): Start of the line in input inp file that indicates the end of the element 
		section of the file.
	elementDamageStartInp (optional)(str): Start of the line in input inp file that indicates the start of the elements 
		in the damage region section of the file.
	elementDamageEndInp (optional)(str): Start of the line in input inp file that indicates the end of the elements 
		in the damage region section of the file.
		
"""

#YOU MUST CHANGE#####################################
#inputName= "Real_Section_with_large_set_37"
#inputName= "Real_Section_with_set_28"
#inputName= "Rat_721_full_w_damage_z"
inputName = "Rat_721_partial_w_dam_smal"

#YOU CAN CHANGE######################################
#core = 1
core = 'max' # Default for all cores

nodeStartInp="*Node"
nodeEndInp	= "*"

elementNormalStartInp = "*Element, type=C3D8"
elementNormalEndInp =  "*"

elementDamageStartInp = "*Elset, elset=DAMAGE"
elementDamageEndInp=	"*"

cohesiveTitle = "*Element, type=COH3D8\n"
elementSetCohesive = "*Elset, elset=COH_ELEM_SET, generate\n"
sectionCohesive = "** Section: Section-0-COH\n\
*Cohesive Section, elset=COH_ELEM_SET, material=DAMAGE, response=TRACTION SEPARATION\n"

#YOU SHOULD NOT #####################################
#_____________________________________
#Module imports

#System and OS modules
import time
import datetime
import os
import multiprocessing as mp

#Other modules
import bisect
import math
import cPickle

#_____________________________________
#Directory and file names
inputFile= "inp/%s.inp"%inputName
outputFile = "%s-output.inp"%inputFile

stamp = time.strftime("%Y-%m-%d %H-%M-%S", time.gmtime())
outputDirectory = "reports/%s-%s" %(inputName,stamp)

#_____________________________________
#Redefining core numbers if left at default
if core is "max":
	core = mp.cpu_count()	 # Default for max number of cores
	print "Using maximum number of cores:", core

#_____________________________________
#Temporary pickle file names
pklFileName = {}
pklFileName['elementList'] = "%s/elementList.pkl"%outputDirectory
pklFileName['elementListNormal'] = "%s/elementListNormal.pkl"%outputDirectory
pklFileName['nodeList'] = "%s/nodeList.pkl"%outputDirectory
pklFileName['elementNumbers'] = "%s/elementNumbers.pkl"%outputDirectory
pklFileName['cohesiveFaces'] = "%s/cohesiveFaces.pkl"%outputDirectory
pklFileName['elementNumberCohesive'] = "%s/elementNumberCohesive.pkl"%outputDirectory
pklFileName['cohesive'] = "%s/cohesive.pkl"%outputDirectory

#_____________________________________
# Global variables that are used to pass large data structures during multiprocesssing

# Large data structures
elementList = None
elementListNormal = None
nodeList = None
elementNumbers = None
cohesiveFaces = None
elementNumberCohesive = None
cohesive = None

# Face orientation arrary
faceOrientation = None

# Bisect search support arrays
nodeListNodeNumber = None
nodeListNodeIndex = None

elementListNormalNumber = None
elementListNormalIndex = None

elementListNumber = None
elementListIndex = None

elementListFaceANumber = None
elementListFaceAIndex = None
elementListFaceBNumber = None
elementListFaceBIndex = None
elementListFaceCNumber = None
elementListFaceCIndex = None

# Node and element starting numbers
cohesiveNodeStartNumber = None
cohesiveElementStartNumber = None

#_____________________________________
# General support functions used throughout the program
def savingTime(step,timeStart,timeEnd):
	"""Writes time elasped by appending to a file.
			
	Args:
		step (str): Tag for the current time being saved.
		timeStart (str): time.gmtime object with the format defined in FMT generated with the starting time.
		timeStop (str): time.gmtime object with the format defined in FMT generated with the ending time.

	The function will attempt to open a file found in "<directory>/time-<inputName>.txt" where
	<directory> and <inputName> are global variables.
	
	Format of time.gmtime() object given as an input is defined individually across multiple areas in the script.
		
	"""
	global outputDirectory
	global inputName
	
	FMT = '%d-%H-%M-%S'
	difference = datetime.datetime.strptime(timeEnd,FMT)-datetime.datetime.strptime(timeStart,FMT)
	with open("%s/time-%s.txt" %(outputDirectory,inputName), 'a') as f:
		f.writelines ("%s: %s\n" %(step, difference))

def sortIntColumnForBisectSearch(unsortedList,column):
	"""Takes a column from an unsorted list, converts it to int, and returns the sorted column and a map of each sorted element to its original index.
			
	Args:
		unsortedList (list): 2D list to be sorted be column
		column (int): Column number to be sorted by.

	Returns:
		sortedListNumber (list): Sorted column values in increasing order.
		sortedListIndex (list): List of len(sortedListNumber) that maps each element in the sorted list back to its original index value.
		
	"""
	# Sort elementList to make searching quicker (for safe measure)
	sortedList= []

	# Grab node column, make it an integer, and its corresponding index value
	for x in range(0,len(unsortedList)):
		sortedList.append([int(unsortedList[x][column]), x])

	# Sort the node column with its index value attached
	sortedList.sort(key = lambda r:r[column])

	# Split back the sorted node column and its old index value to prepare for bisect binary searching
	sortedListNumber = []
	sortedListIndex = []
	for x in range(0,len(sortedList)):
		sortedListNumber.append(sortedList[x][0])
		sortedListIndex.append(sortedList[x][1])
	
	return [sortedListNumber,sortedListIndex]

def bisectSearchSortedList(searchElement, sortedListElements, sortedListIndex):
	"""Applies a binary search using the bisect module on a sorted list and returns its index in the original unsorted list.
			
	Args:
		searchElement (obj): Object to look for in the sorted list
		sortedListElements (list): Sorted list of objects be be searched
		sortedListIndex (list): List of len(sortedListNumber) that maps each element in the sorted list back to its original index value.

	Returns:
		index (int): Original index value of the result found through binary searching
	
	Module uses bisect_left from the bisect module to perform binary searching. As a result, the returned index value will not point to the 
	object that was searched for in the original unsorted list if the value being searched could not be found. Does not return all index values
	containing the value that is being searched, but will return at least one proper index value if object is found.
		
	"""
	index = bisect.bisect_left(sortedListElements,searchElement)
	
	if index >= len(sortedListElements):
		return 0
	
	return sortedListIndex[index]
	
def sortElementListForFaceBisectSearch(unsortedList,face):
	"""Sort a list in increasing order according to the 4 column given. Returns the sorted columns as well as its original index value.
			
	Args:
		unsortedList (list): Unsrted list to be sorted
		face (list): A 4 length long list of ints dictating which columns to sort the unsortedList by.
	
	Returns:
		sortedListNumber (list): Sorted columns in increasing order.
		sortedListIndex (list): List of len(sortedListNumber) that maps each element in the sorted list back to its original index value.
		
	"""
	sortedList= []

	# Grab node column, make it an integer, and its corresponding index value
	for x in range(0,len(unsortedList)):
		sortedList.append([unsortedList[x][face[0]],unsortedList[x][face[1]],unsortedList[x][face[2]],unsortedList[x][face[3]], x])

	# Sort the node column with its index value attached
	sortedList.sort(key = lambda r:(r[0], r[1], r[2], r[3]))

	# Split the sorted node column and its old index value to prepare for bisect binary searching
	sortedListNumber = []
	sortedListIndex = []
	for x in range(0,len(sortedList)):
		sortedListNumber.append([sortedList[x][0],sortedList[x][1],sortedList[x][2],sortedList[x][3]])
		sortedListIndex.append(sortedList[x][4])
	
	return [sortedListNumber,sortedListIndex]

# Support functions for copying data from old inp file to new inp file
def copyFromFileLineNumber(inputFileName,outputFilePointer, start, stop):
	"""Copys file lines from one file to a new file.
			
	Args:
		inputFileName (str): File name of file containing lines to be copied
		outputFilePointer (str): Opened file pointer to write lines to be copied
		start (int): Starting line number to start copy from
		stop (int): Ending line number to stop copying
		
	"""
	# Account for the 1 off index between line number inf file and line number from read in
	start = start - 1
	stop = stop - 1

	with open(inputFileName) as file:
		for i, line in enumerate(file):
			if i >= start and i < stop:
				outputFilePointer.writelines(line)
			if i >= stop:
				break

def endOfFileLineNumber(inputFileName):
	"""Gets the total number of lines in a file. Function made for clarity.
			
	Args:
		inputFileName (str): File name of the file to get total number of lines.
		
	Returns:
		lines (int): Total number of lines in a file.
	"""
	lines = 0
	with open(inputFileName) as file:
		lines = sum(1 for line in file)
	return lines

#Support functions for pickling and unpickling	
def pklObj(obj, fileName):
	"""Pickles a data stucture to disk for storage.
			
	Args:
		obj (obj): Object to store to disk
		fileName (str): File name to store object in pickled format

	Returns:
		[] (list): Empty list.
		
	"""
	pklFP = open(fileName, 'wb')
	cPickle.dump(obj, pklFP, -1)
	pklFP.close()
	return []
	
def unpklObj(fileName):
	"""Unpickles a data stucture from disk for use.
			
	Args:
		fileName (str): File name where the pickled object is stored

	Returns:
		obj (obj): The unpickled object for use.
		
	WARNING: (As copied from the manual for the pickle module)
	The pickle module is not secure against erroneous or maliciously constructed data. 
	Never unpickle data received from an untrusted or unauthenticated source.
	
	"""
	pklFP = open(fileName, 'rb')
	obj = cPickle.load(pklFP)
	pklFP.close()
	return obj
	
def delFile(fileName):
	"""Deletes a file. Function made for clarity.
			
	Args:
		fileName (str): File name of file to be deleted

	Returns:
		[] (list): Empty list.
		
	"""
	os.remove(fileName)
	return [];	

def findInpSectionStartEnd(startLineHeader, endLineHeader, fileName):
		headerLength = len(startLineHeader)
		enderLength = len(endLineHeader)
		
		headerLineNum = -1
		enderLineNum = -1
		
		with open(fileName) as inpFile:
			for num, line in enumerate(inpFile, 1):
		
				if startLineHeader == line[:headerLength]:
					headerLineNum = num
					
				if endLineHeader == line [:enderLength]:
					enderLineNum = num
					
				if enderLineNum > headerLineNum and headerLineNum > 0:
					break
		
		return [headerLineNum, enderLineNum]
	
#_____________________________________
# Subfunctions used by processes to perform multiprocessing tasks

# Called in step 4

def init(_elementListNormal, _elementListNormalNumber, _elementListNormalIndex):
	"""Fuction to initialize global read only variables for each process.
			
	Args:
		_elementListNormal (list): List that contains the list of all elements and their defining node numbers
		_elementListNormalNumber (list): List that contains element numbers in elementListNormal sorted in increasing order
		_elementListNormalIndex (list): Paired list corresponding with _elementListNormalNumber which points to index of the element number in _elementListNormal
	
	"""
	
	global elementListNormal
	global elementListNormalNumber
	global elementListNormalIndex
	
	elementListNormal = _elementListNormal
	elementListNormalNumber = _elementListNormalNumber
	elementListNormalIndex = _elementListNormalIndex
		
def check(element):
	"""Fuction processed by individual processes to search for an element from the enitre list of elements
			
	Args:
		element (string): String containing the number of the element we want to search for in elementListNormal
		
	Returns:
		elementListNormalNode (list): Found element and its defining nodes. Will return wrong element if element being searched does not exist
	
	"""
	
	# Search for the element and its defining nodes from sorted list using bisect search
	elementNumber = int(element)
	index = bisectSearchSortedList(elementNumber, elementListNormalNumber, elementListNormalIndex)
	elementListNormalNode = elementListNormal[index]

	# Check to make sure the element retireved is the one we want (search can fail if element does not exist in elementListNormal)
	if elementListNormalNode[0] == elementNumber:
		return elementListNormalNode
		
	return []

def func(elementNumbers, elementListNormal, elementListNormalNumber, elementListNormalIndex):
	"""Fuction to set up the multiprocess procedure to get elements in the damage zone from list of normal elements.
		
	Args:
		elementNumbers (list): List of element numbers to have cohesive elements inserted into
		elementListNormal (list): List that contains the list of all elements and their defining node numbers
		elementListNormalNumber (list): List that contains element numbers in elementListNormal sorted in increasing order
		elementListNormalIndex (list): Paired list corresponding with _elementListNormalNumber which points to index of the element number in _elementListNormal
	
	Returns:
		elementList (list): List of elements and defining node numbers to have coheesive elements inserted into.
	
	"""
	
	#Retrieve the elements and their defining nodes given element numbers defined in elementNumbers. Store result in elementList
	pool = mp.Pool(processes=core, initializer=init, initargs=(elementListNormal,elementListNormalNumber,elementListNormalIndex,))
	
	results = []
	
	for k in elementNumbers:
		results.append(pool.apply_async(check,(k,)))
	pool.close()
	pool.join()
	
	elementList = []
	
	for result in results:
		elementListNode = result.get()
		if elementListNode != None:
			elementList.append(elementListNode)
	
	return elementList

# Called in Step 5 and 6

def init2(_elementList, _faceOrientation, _elementListFaceANumber, _elementListFaceAIndex, _elementListFaceBNumber, _elementListFaceBIndex, _elementListFaceCNumber, _elementListFaceCIndex):
	"""Fuction to initialize global read only variables for each process.
			
	Args:
		_elementList (list): List of elements and defining node numbers to have coheesive elements inserted into
		_faceOrientation (dict): Dictionary containing all possible face orientations for an element defined by node index number
		_elementListFaceANumber (list): List that contains element numbers in elementList sorted in increasing order according to orientation A
		_elementListFaceAIndex (list): Paired list corresponding with elementListFaceANumber which points to index of the element number in _elementListNormal
		_elementListFaceBNumber (list): List that contains element numbers in elementList sorted in increasing order according to orientation A
		_elementListFaceBIndex (list): Paired list corresponding with elementListFaceBNumber which points to index of the element number in _elementListNormal
		_elementListFaceCNumber (list): List that contains element numbers in elementList sorted in increasing order according to orientation A
		_elementListFaceCIndex (list): Paired list corresponding with elementListFaceCNumber which points to index of the element number in _elementListNormal
	
	"""
	
	global elementList 
	global faceOrientation
	
	global elementListFaceANumber
	global elementListFaceAIndex
	
	global elementListFaceBNumber
	global elementListFaceBIndex
	
	global elementListFaceCNumber
	global elementListFaceCIndex
	
	elementList = _elementList
	faceOrientation = _faceOrientation
	
	elementListFaceANumber = _elementListFaceANumber
	elementListFaceAIndex = _elementListFaceAIndex
	
	elementListFaceBNumber = _elementListFaceBNumber
	elementListFaceBIndex = _elementListFaceBIndex
	
	elementListFaceCNumber = _elementListFaceCNumber
	elementListFaceCIndex = _elementListFaceCIndex
		
	
def check2(elem):
	"""Fuction processed by individual processes to search for cohesive faces from list of elements in the damage zone.
			
	Args:
		elem (string): String containing the element in the damage zone we want to search faces for.
		
	Returns:
		cohesiveFacesList (list): Found element, its connected element, and the shared cohesive face nodes. 
	
	"""
	
	cohesiveFacesList = []

	#combination A:
	#Search for face A backward combination from sorted elementList in conbimation A forward
	face = [elem[i] for i in faceOrientation['Ab']]
	index = bisectSearchSortedList(face, elementListFaceANumber, elementListFaceAIndex)
	elementListEntry = elementList[index]

	if face == [elementListEntry[i] for i in faceOrientation['Af']]:
		cohesiveFacesList.append([elementListEntry[0], 'Af'] + face)
		cohesiveFacesList.append([elem[0], 'Ab']  + face)
			
	#combination B:
	#Search for face B backward combination from sorted elementList in conbimation B forward
	face = [elem[i] for i in faceOrientation['Bb']]
	index = bisectSearchSortedList(face, elementListFaceBNumber, elementListFaceBIndex)
	elementListEntry = elementList[index]

	if face == [elementListEntry[i] for i in faceOrientation['Bf']]:
		cohesiveFacesList.append([elementListEntry[0], 'Bf'] + face)
		cohesiveFacesList.append([elem[0], 'Bb']  + face)

	#combination C:
	#Search for face C backward combination from sorted elementList in conbimation C forward
	face = [elem[i] for i in faceOrientation['Cb']]
	index = bisectSearchSortedList(face, elementListFaceCNumber, elementListFaceCIndex)
	elementListEntry = elementList[index]

	if face == [elementListEntry[i] for i in faceOrientation['Cf']]:
		cohesiveFacesList.append([elementListEntry[0], 'Cf'] + face)
		cohesiveFacesList.append([elem[0], 'Cb']  + face)
	
	return cohesiveFacesList

def func2(elementList, faceOrientation, elementListFaceANumber, elementListFaceAIndex, elementListFaceBNumber, elementListFaceBIndex, elementListFaceCNumber, elementListFaceCIndex):
	"""Fuction to set up the multiprocess procedure to find cohesive faces from elements in the damange zone.
		
	Args:
		elementList (list): List of elements and defining node numbers to have coheesive elements inserted into
		faceOrientation (dict): Dictionary containing all possible face orientations for an element defined by node index number
		elementListFaceANumber (list): List that contains element numbers in elementList sorted in increasing order according to orientation A
		elementListFaceAIndex (list): Paired list corresponding with elementListFaceANumber which points to index of the element number in _elementListNormal
		elementListFaceBNumber (list): List that contains element numbers in elementList sorted in increasing order according to orientation A
		elementListFaceBIndex (list): Paired list corresponding with elementListFaceBNumber which points to index of the element number in _elementListNormal
		elementListFaceCNumber (list): List that contains element numbers in elementList sorted in increasing order according to orientation A
		elementListFaceCIndex (list): Paired list corresponding with elementListFaceCNumber which points to index of the element number in _elementListNormal
	
	Returns:
		cohesiveFaces (list): List of all cohesive faces defined as [element_number, orientation, node_number, node_number2, ..., node_numberN]
	
	Corresponding node index numbers for each face can be found through faceOrientation[orientation].
	
	"""
	
	#Define all connected faces in cohesive zone region and their corresponding element, face orientation, and nodes
	pool2 = mp.Pool(processes=core,initializer=init2, initargs=(elementList, faceOrientation, elementListFaceANumber, elementListFaceAIndex, elementListFaceBNumber, elementListFaceBIndex, elementListFaceCNumber, elementListFaceCIndex,))
	
	results = []
	
	for elem in elementList:
		results.append(pool2.apply_async(check2,(elem,)))
	pool2.close()
	pool2.join()
	
	cohesiveFaces = []
	
	for result in results:
		cohesiveFacesList = result.get()
		cohesiveFaces.extend(cohesiveFacesList)
		
	return cohesiveFaces
	
	
# Called in step 7-1
def init3(_cohesiveFaceNodes):
	"""Fuction to initialize global read only variables for each process.
			
	Args:
		_cohesiveFaceNodes (list): List of cohesive faces
	
	"""

	global cohesiveFaceNodes 
	
	cohesiveFaceNodes = _cohesiveFaceNodes
		
def check3(elem):
	"""Fuction processed by individual processes to search each node found in each element in the damage zone to see which nodes make up of cohesive faces.
			
	Args:
		elem (list): Element and nodes defining the element to be searched for cohesive face node numbers.
		
	Returns:
		support (list): 2D list of index numbers and element numbers to be added to nodeSupport
	
	"""
	
	support = []
	checkNodes = elem[1:]
	
	for i in checkNodes:
		index = bisect.bisect_left(cohesiveFaceNodes, i)
		if index < len(cohesiveFaceNodes) and cohesiveFaceNodes[index] == i:
			support.append([index, elem[0]])
	return support

def func3(elementList, cohesiveFaces):
	"""Fuction to set up the multiprocess procedure to find each element in the damage zone that connects with an affected node.
		
	Args:
		elementList (list): List of elements and defining node numbers to have coheesive elements inserted into
		cohesiveFaceNodes (list): List of cohesive faces
	
	"""
	# Information reordering to grab only the cohesive element and their face nodes. Also removes duplicates (if any)
	cohesiveFaces = [([col[0]] + col[2:]) for col in cohesiveFaces]
	
	#Make a list of all unique nodes that make up of cohesive faces and sort them
	cohesiveFaces = map(lambda x: x[1:], cohesiveFaces)
	cohesiveFaces = list(set(int(i) for j in cohesiveFaces for i in j))
	cohesiveFaces.sort()
	
	pool2 = mp.Pool(processes=core,initializer=init3, initargs=(cohesiveFaces,))

	results = []
	
	#Go through elementList and check if any of the nodes lie in the unqiue list of nodes in the list of cohesive faces. For each that appear, insert to support.
	for elem in elementList:
		results.append(pool2.apply_async(check3,(elem,)))
	pool2.close()
	pool2.join()
	
	#Make a list of elements with a cohesive face and define which nodes are affected by inserting cohesive nodes
	nodeSupport = [[i] for i in cohesiveFaces] #Variable to store all cohesive nodes and cohesive elements attached to those nodes
	
	num = 0
	for result in results:
		
		support = result.get()
		
		if support != None:
			for i in range(len(support)):
				nodeSupport[support[i][0]].extend([support[i][1]])
			
	return nodeSupport
	
		
# Called in step 7-2
def init4(_elementList, _elementListNumber, _elementListIndex, _cohesiveNodeStartNumber):
	"""Fuction to initialize global read only variables for each process.
			
	Args:
		_elementList (list): List of element numbers to have cohesive elements inserted into
		_elementListNumber (list): List that contains element numbers in elementList sorted in increasing order
		_elementListIndex (list): Paired list corresponding with _elementListNumber which points to index of the element number in _elementList
		_cohesiveNodeStartNumber (list): Starting index number when creating cohesive nodes
	
	"""
	
	global elementList
	global elementListNumber
	global elementListIndex
	global cohesiveNodeStartNumber
	
	elementList = _elementList
	elementListNumber = _elementListNumber
	elementListIndex = _elementListIndex
	cohesiveNodeStartNumber = _cohesiveNodeStartNumber
	
def check4(n):
	"""Fuction processed by individual processes to search for elements attached to each cohesive face node.
			
	Args:
		n (list): Node number and list of elements attached to the node.
		
	Returns:
		[tempNode, fixNode] (list): lement number and node that needs to be fixed as well as new nodes to be added to the nodeList
		
	Format of n = [nodenumber, element1, element2,..., elementN]. Number of nodes in n will range from 2 to 8 nodes.
	
	"""
	tempNode = []
	fixNode = []
	
	#Increment number for each element that uses the same node number
	increase = cohesiveNodeStartNumber
	
	#For each element that uses the node number
	for r in n[2:]:

		#Find the element in elementList using binary search
		index = bisectSearchSortedList(r, elementListNumber, elementListIndex)
		elementListNode = elementList[index]

		if r == elementListNode[0]: #r is the element number
		
			#Increase the node number by the increment number for each element found and record this change for later modifications
			for k in range(1,9):
				if	n[0] == elementListNode[k]:
					# Store changes to be made into queue for editing elementList at main program
					fixNodeNumber = [index,k,(n[0] + increase)]
					fixNode.append(fixNodeNumber)
					tempNode.append(n[0]+increase)
			increase = increase + cohesiveNodeStartNumber
	return [tempNode, fixNode]
				   
def func4(nodeSupport, elementList, elementListNumber, elementListIndex, cohesiveNodeStartNumber):
	"""Fuction to set up the multiprocess procedure to renumber repeated nodes that make up of cohesive faces
	
	Args:
		nodeSupport (list): List of nodes and affected elements that need to be modified.
		elementList (list): List of element numbers to have cohesive elements inserted into
		elementListNumber (list): List that contains element numbers in elementList sorted in increasing order
		elementListIndex (list): Paired list corresponding with elementListNumber which points to index of the element number in elementList
		cohesiveNodeStartNumber (list): Starting index number when creating cohesive nodes

	Returns:
		tempNodeNode (list): List of newly created node numbers that need their positions to be defined
		
	"""
	pool2 = mp.Pool(processes=core, initializer = init4, initargs=(elementList, elementListNumber, elementListIndex, cohesiveNodeStartNumber,))
	
	results = []
	
	for a in nodeSupport:
		results.append(pool2.apply_async(check4,args=(a,)))
	pool2.close()
	pool2.join()
	
	tempNodeNode = []
	
	for result in results:
		(tempNodes, fixElementNodes) = result.get()
		
		tempNodeNode.append(tempNodes)
		
		#Write changes marked by the processes into elementList
		for i in range(len(fixElementNodes)):
			elementList[fixElementNodes[i][0]][fixElementNodes[i][1]] = fixElementNodes[i][2]
			
	return tempNodeNode

# Called in step 7-3
def init5(_nodeList, _nodeListNodeNumber, _nodeListNodeIndex, _cohesiveNodeStartNumber):
	"""Fuction to initialize global read only variables for each process.
			
	Args:
		_nodeList (list): List of node numbers and their positions
		_nodeListNodeNumber (list): List that contains node numbers in nodeList sorted in increasing order
		_nodeListNodeIndex (list): Paired list corresponding with _nodeListNodeNumber which points to index of the element number in _nodeList
		_cohesiveNodeStartNumber (list): Starting node number when creating cohesive nodes
	
	"""
	
	global nodeList
	global nodeListNodeNumber
	global nodeListNodeIndex
	global cohesiveNodeStartNumber

	nodeList = _nodeList
	nodeListNodeNumber = _nodeListNodeNumber
	nodeListNodeIndex = _nodeListNodeIndex
	cohesiveNodeStartNumber = _cohesiveNodeStartNumber
	
def check5(r):
	"""Fuction processed by individual processes to search for the coordinates of the original node, copy those coordinates to newly created nodes and add them to nodeList.
			
	Args:
		r (string): Newly created node number.
		
	Returns:
		[r,nodeList[index][1],nodeList[index][2],nodeList[index][3]] (list): Newly created node number entry to be added to nodeList.
	
	"""
	
	# Calculate quotient and remainder of modified node number
	nodeNumCheck = int(r)
	quotientNodeNumber = nodeNumCheck/cohesiveNodeStartNumber
	remainderNodeNumber = nodeNumCheck%cohesiveNodeStartNumber

	# Make sure modified node number falls within correct numbering conventions
	if quotientNodeNumber >= 1 and quotientNodeNumber < 8:

		# Find original node number from sorted list
		index = bisectSearchSortedList(remainderNodeNumber, nodeListNodeNumber, nodeListNodeIndex)
		nodeNum = nodeList[index][0]

		# Check to make sure node number found at index matches the original node number we are looking for (could be skipped)
		if int(nodeNum) == remainderNodeNumber:
			return [r,nodeList[index][1],nodeList[index][2],nodeList[index][3]]

	#Should never get here
	return [r, 0 ,0, 0]

def func5(tempNodeNode, nodeList, nodeListNodeNumber, nodeListNodeIndex, cohesiveNodeStartNumber):
	"""Fuction to set up the multiprocess procedure to get create new node entries for the newly created nodes.
	
	Args:
		tempNodeNode (list): List of cohesive node numbers that need to be created
		nodeList (list): List of node numbers and their positions
		nodeListNodeNumber (list): List that contains node numbers in nodeList sorted in increasing order
		nodeListNodeIndex (list): Paired list corresponding with nodeListNodeNumber which points to index of the element number in nodeList
		cohesiveNodeStartNumber (list): Starting index number when creating cohesive nodes
	
	"""
	
	pool2 = mp.Pool(processes=core, initializer = init5, initargs=(nodeList,nodeListNodeNumber, nodeListNodeIndex, cohesiveNodeStartNumber,))
	
	results = []
	
	for a in tempNodeNode:
		for r in a:
			results.append(pool2.apply_async(check5,(r,)))
	pool2.close()
	pool2.join()

	for result in results:
		nodeListTemp = result.get()
		
		# Add the newly create node numbers and their coordinates into the nodeList
		nodeList.append(nodeListTemp)

# Called in step 8
# Support functions for multiprocessing for this step
def init6(_elementListNormal, _elementListNormalNumber, _elementListNormalIndex):
	"""Fuction to initialize global read only variables for each process.
	
	Args:
		elementListNormal (list): List that contains the list of all elements and their defining node numbers
		elementListNormalNumber (list): List that contains element numbers in elementListNormal sorted in increasing order
		elementListNormalIndex (list): Paired list corresponding with _elementListNormalNumber which points to index of the element number in _elementListNormal
	
	"""
	global elementListNormal
	global elementListNormalNumber
	global elementListNormalIndex

	elementListNormal = _elementListNormal
	elementListNormalNumber = _elementListNormalNumber
	elementListNormalIndex = _elementListNormalIndex
	
def check6(elementListNode):
	"""Fuction processed by individual processes to search for the element with modified node numbers from the complete list of elements.
			
	Args:
		elementListNode (list): Element node entry with defining nodes that have been modified to add cohesive elements.
		
	Returns:
		[index, elementListNormalNode] (list): Index of the element to be modified and its new node numbers.
	
	"""
	index = bisectSearchSortedList(elementListNode[0], elementListNormalNumber, elementListNormalIndex)
	elementListNormalNode = elementListNormal[index]

	if elementListNode[0] == elementListNormalNode[0]:
		for k in range(1,len(elementListNode)):
			elementListNormalNode[k] = elementListNode[k]
		return [index, elementListNormalNode]

	# Should not go here
	return [index, elementListNormalNode]


def func6(elementList, elementListNormal, elementListNormalNumber, elementListNormalIndex):
	"""Fuction to set up the multiprocess procedure to find and modify elements in the normal element list to add cohesive elements.
		
	Args:
		elementNumbers (list): List of element numbers to have cohesive elements inserted into
		elementListNormal (list): List that contains the list of all elements and their defining node numbers
		elementListNormalNumber (list): List that contains element numbers in elementListNormal sorted in increasing order
		elementListNormalIndex (list): Paired list corresponding with _elementListNormalNumber which points to index of the element number in _elementListNormal
	
	"""
	
	pool2 = mp.Pool(processes=core, initializer = init6, initargs=(elementListNormal,elementListNormalNumber, elementListNormalIndex,))
	
	results = []
	
	for elementListNode in elementList:
		results.append(pool2.apply_async(check6,(elementListNode,)))
	pool2.close()
	pool2.join()

	for result in results:
		fixElementListNormal = result.get()
		
		# Apply the changes found in node ordering to cohseive nodes
		elementListNormal[fixElementListNormal[0]] = fixElementListNormal[1]
		
# Called in step 9
# Support functions for multiprocessing for this step
def init7(_elementList, _elementListNumber, _elementListIndex, _faceOrientation):
	"""Fuction to initialize global read only variables for each process.
			
	Args:
		_elementList (list): List of element numbers to have cohesive elements inserted into
		_elementListNumber (list): List that contains element numbers in elementList sorted in increasing order
		_elementListIndex (list): Paired list corresponding with _elementListNumber which points to index of the element number in _elementList
		_faceOrientation (dict): Dictionary containing all possible face orientations for an element defined by node index number
	
	"""

	global elementList
	global elementListNumber
	global elementListIndex
	global faceOrientation
	
	elementList = _elementList
	elementListNumber = _elementListNumber
	elementListIndex = _elementListIndex
	faceOrientation = _faceOrientation
	
def check7(cohesiveFacePair):
	"""Fuction processed by individual processes to search for the elements that make up the cohesive face pairs and create the cohesive element.
			
	Args:
		cohesiveFacePair (list): A list containing a pair of cohesiveFace elements that combine to form a cohesive element.
		
	Returns:
		cohesiveElement (list): Fully formed cohesive element from the cohesiveFace pair.
	
	"""
	# Seperate out the first face and second faces that make up the cohesive element
	[firstFace, secondFace] = cohesiveFacePair

	# For each face, find the element attached to each side of each cohesive face from elementList
	index = bisectSearchSortedList(firstFace[0], elementListNumber, elementListIndex)
	firstFaceElementNode = elementList[index]
	
	index = bisectSearchSortedList(secondFace[0], elementListNumber, elementListIndex)
	secondFaceElementNode = elementList[index]
	
	# Reconstruct the cohesive element based on orientation information saved from step 5 and 6
	
	# We know the node numbers we want and their final positions based on the orientation of the first and second faces (defined in face[1])
	
	# Get the element numbers relevant for creating the cohesive nodes for the first and second faces
	firstFaceCohesiveNodes = [firstFaceElementNode[i] for i in faceOrientation[firstFace[1]]]
	secondFaceCohesiveNodes = [secondFaceElementNode[i] for i in faceOrientation[secondFace[1]]]
	
	# Create the cohesive element by placing the 2 faces back to back
	cohesiveElement = [0] + firstFaceCohesiveNodes + secondFaceCohesiveNodes
	
	# Return the reconstructed element
	return cohesiveElement

def func7(cohesiveFaces, elementList, elementListNumber, elementListIndex, faceOrientation):
	"""Fuction to set up the multiprocess procedure to create the cohesive element from the cohesive faces.
	
	Args:
		cohesiveFaces (list): List of cohesive faces sorted by corresponding pairs of cohesive faces
		elementList (list): List of element numbers to have cohesive elements inserted into
		elementListNumber (list): List that contains element numbers in elementList sorted in increasing order
		elementListIndex (list): Paired list corresponding with elementListNumber which points to index of the element number in elementList
		faceOrientation (dict): Dictionary containing all possible face orientations for an element defined by node index number
	
	cohesiveFaces is a global variable containing the list of cohesive faces that make up the cohesive elements. Note that the 
	structure of cohesiveFaces make it such that each pair of faces strating from index 0 form a cohesive element with each other
	(i.e: (cohesiveFaces[0], cohesiveFaces[1]) form a pair to make a cohesive element as will (cohesiveFaces[2n], cohesiveFaces[2n+1])).
	
	"""
	createFaceElement = False
	firstFace = []
	
	pool2 = mp.Pool(processes=core, initializer = init7, initargs=(elementList, elementListNumber, elementListIndex, faceOrientation,))
	
	results = []
	
	for cohesiveFaceNode in cohesiveFaces:
		
		if createFaceElement:
			results.append(pool2.apply_async(check7,([firstFace,cohesiveFaceNode],)))
			createFaceElement = False
			
		else:
			firstFace = cohesiveFaceNode
			createFaceElement = True
		
	pool2.close()
	pool2.join()
	
	cohesive = []
	
	for result in results:
		cohesive.append(result.get())
		
	return cohesive

def generateCohesiveElements():
	"""Main function for generating cohesive elements.
	
	"""
	# Predefine global variables to be used in conjunction with processes
	# (Make sure to take the "check" and "log" functions out of this function
	
	# Main program
	#____________________STEP 0______________________________
	""" Create the results folder where results will be stored.

	"""
	if not os.path.exists(outputDirectory):
		os.makedirs(outputDirectory)

	#____________________STEP 1 and 2______________________________
	""" Identify the individual sections of the files and store their starting and ending line numbers. Stop script if any section is not clearly defined.

	"""
	print "Step1and2"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1

	#Preassign line numbers to each header and ending to identify if a section is incomplete
	nodeStart = -1
	nodeEnd = -1
	elementDamageStart = -1
	elementDamageEnd = -1
	elementNormalStart = -1
	elementNormalEnd = -1

	#Go through the stored lines and find the line number each header/ending could be found

	#mark the start of nodes
	[nodeStart, nodeEnd] = findInpSectionStartEnd(nodeStartInp, nodeEndInp, inputFile)

	#marking the start and end of Damage elements
	[elementDamageStart, elementDamageEnd] = findInpSectionStartEnd(elementDamageStartInp, elementDamageEndInp, inputFile)

	#marking the start and end of Normal elements
	[elementNormalStart, elementNormalEnd] = findInpSectionStartEnd(elementNormalStartInp, elementNormalEndInp, inputFile)

	#If any of the start and end sections were not found, display an error and exit:
	if -1 in [nodeStart, nodeEnd, elementDamageStart, elementDamageEnd, elementNormalStart, elementNormalEnd]:
		
		print "\nOne or more section(s) is/are missing. Line number of each sections found are listed below:"
		print "	   node = "+str(nodeStart)+" to "+str(nodeEnd)
		print "	   elementDamage = "+str(elementDamageStart)+" to "+str(elementDamageEnd)
		print "	   elementNormal = "+str(elementNormalStart)+" to "+str(elementNormalEnd)
		print ""
		
		if nodeStart is -1:
			print "Start of node section was not found. Missing header starting with:\n	   ", nodeStartInp
			
		if nodeEnd is -1:
			print "End of node section was not found. Missing header starting with:\n	 ", nodeEndInp
			
		if elementDamageStart is -1:
			print "Start of damage section was not found. Missing header starting with:\n	 ", elementDamageStartInp
		
		if elementDamageEnd is -1:
			print "End of damage section was not found. Missing header starting with:\n	   ", elementDamageEndInp
			
		if elementNormalStart is -1:
			print "Start of element section was not found. Missing header starting with:\n	  ", elementNormalStartInp
			
		if elementNormalEnd is -1:
			print "End of element section was not found. Missing header starting with:\n	", elementNormalEndInp
		
		return

		
		
	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("Step1and2",time1,time2)
	#____________________STEP 3______________________________
	""" Parsing and storing the nodes, elements and damage elements into lists for easy access. 

	"""
	print "Step3"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1

	#storing nodes from file
	nodeList = []
	with open(inputFile) as fp:
		nodeEndTemp = nodeEnd - 1
		for num, line in enumerate(fp):
			if num < nodeStart:
				continue
			if num >= nodeEndTemp:
				break
			d = line.strip().split(",")
			nodeList.append(d) 

	#getting rid of the extra space in the list
	for z in range (0, len(nodeList)):
		for k in range (0,4):
			nodeList[z][k] = nodeList[z][k].strip()

	# Sort nodeList to make searching quicker (for safe measure)
	nodeListNodeNumber = []
	nodeListNodeIndex = []
	[nodeListNodeNumber, nodeListNodeIndex] = sortIntColumnForBisectSearch(nodeList,0)

	# Find the largest node number to identify what the starting number for new nodes should be
	cohesiveElementStartNumber = int(10**(math.floor(math.log10(nodeListNodeNumber[-1]))+1))

	#Pickle object to disk for later use
	nodeList = pklObj(nodeList, pklFileName['nodeList'])

	##############################################
	#Storing damage elments from file
	temp = []
	with open(inputFile) as fp:
		elementEndTemp = elementDamageEnd - 1
		for num, line in enumerate(fp):
			if num < elementDamageStart:
				continue
			if num >= elementEndTemp:
				break
			d = line.strip().split(",")
			temp = d + temp

	#getting rid of empty entry
	elementNumbers = filter(None, temp)

	#getting rid of the extra space in the list
	for z in range (0, len(elementNumbers)):
		elementNumbers[z] = int(elementNumbers[z].strip())
		
	#Correcting for if damage elements is a range rather than a list
	if len(elementNumbers) == 3 and elementNumbers[0] == elementNumbers[2]:
		elementNumbers = range(elementNumbers[0], elementNumbers[1] + 1)

	#Pickle object to disk for later use	
	elementNumbers = pklObj(elementNumbers, pklFileName['elementNumbers'])

	##############################################
	#Storing normal elments from file
	elementListNormal = []
	with open(inputFile) as fp:
		elementNormalEndTemp = elementNormalEnd - 1
		for num, line in enumerate(fp):
			if num < elementNormalStart:
				continue
			if num >= elementNormalEndTemp:
				break
			d = line.strip().split(",")
			elementListNormal.append(d)

	#getting rid of the extra space in the list
	for z in range (0, len(elementListNormal)):
		for k in range (0,9):
			elementListNormal[z][k] = int(elementListNormal[z][k].strip())

	# Sort elementListNormal by node number to prepare for binary search later on in the program
	elementListNormalNumber = []
	elementListNormalIndex = []
	[elementListNormalNumber, elementListNormalIndex] = sortIntColumnForBisectSearch(elementListNormal,0)		

	# Find the largest element number to identify what the starting number for new elements should be
	cohesiveNodeStartNumber = int(10**(math.floor(math.log10(elementListNormalNumber[-1]))+1))

	#Pickle object to disk for later use
	elementListNormal = pklObj(elementListNormal, pklFileName['elementListNormal'])

	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("Step3",time1,time2)
	#____________________STEP 4______________________________
	""" For each element in the damage zone, grab the element and its nodes and add them to elementList for processing.

	"""

	print "Step4"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1

	##########################################################################################

	# Unpickle elementListNormal for use
	elementListNormal = unpklObj(pklFileName['elementListNormal'])

	# Unpickle elementNumbers for use
	elementNumbers = unpklObj(pklFileName['elementNumbers'])

	# Grab the damanged elements and their neighbouring nodes from the list of all elements and store them in elementList
	elementList = []

	elementList = func(elementNumbers, elementListNormal, elementListNormalNumber, elementListNormalIndex)

	# Sort elementList by node number to prepare for binary search later on in the program
	elementListNumber = []
	elementListIndex = []
	[elementListNumber, elementListIndex] = sortIntColumnForBisectSearch(elementList,0)

	# Pickle elementListNormal for later use
	elementListNormal = pklObj(elementListNormal, pklFileName['elementListNormal'])

	# Pickle elementNumbers for later use
	elementNumbers = pklObj(elementNumbers, pklFileName['elementNumbers'])

	##########################################################################################
	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("Step4",time1,time2)

	#____________________STEP 5 and 6______________________________
	""" Find all the faces between all elements defined in the damage zone.

		Each element can have 6 possible faces that is shared with another element. We check only 3 of those faces in eace element
		in the damage zone to see if those faces connect with an element in the damage zone. If it does, append the current element
		being checked as well as the element which share the face being checked to the cohesiveFaces list.

	"""
	print "Step5and6"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1
	##########################################################################################
	# For every damage element, check if the forward facing faces are connected to another damanged element. If it is, then add it to the list.
	cohesiveFaces = []	#Global variable to store element number and cohesive face node for each connecting element in the damage zone

	# Sort elementList by forward face orientation to prepare for binary search

	# Define face orientation (accounting for element number in col[0]) used for generating cohesive elements in the damage zone
	faceOrientation = { 'Af': [5,6,7,8], 'Ab': [1,2,3,4],\
						'Bf': [3,4,8,7], 'Bb': [2,1,5,6],\
						'Cf': [2,3,7,6], 'Cb': [1,4,8,5] }	
	
	# Combination A
	elementListFaceANumber = []
	elementListFaceAIndex = []
	[elementListFaceANumber, elementListFaceAIndex] = sortElementListForFaceBisectSearch(elementList,faceOrientation['Af'])

	# Combination B
	elementListFaceBNumber = []
	elementListFaceBIndex = []
	[elementListFaceBNumber, elementListFaceBIndex] = sortElementListForFaceBisectSearch(elementList,faceOrientation['Bf'])

	# Combination C
	elementListFaceCNumber = []
	elementListFaceCIndex = []
	[elementListFaceCNumber, elementListFaceCIndex] = sortElementListForFaceBisectSearch(elementList,faceOrientation['Cf'])

	# Main function of this step
	cohesiveFaces = func2(elementList, faceOrientation, elementListFaceANumber, elementListFaceAIndex, elementListFaceBNumber, elementListFaceBIndex, elementListFaceCNumber, elementListFaceCIndex)

	#Clean up of global variables that have no use anymore
	elementListFaceANumber = []
	elementListFaceAIndex = []

	elementListFaceBNumber = []
	elementListFaceBIndex = []

	elementListFaceCNumber = []
	elementListFaceCIndex = []

	#saving the pairNodes
	with open("%s/pairNodes-%s.txt" %(outputDirectory,inputName), 'w') as f:
		for k in cohesiveFaces:
			f.writelines ("%s\n" %k)

	##########################################################################################
	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "############################"
	savingTime("Step5and6",time1,time2)	 

	#____________________STEP 7______________________________  
	""" Renumber each node in each element attached to a cohesive face so that the node numbers are not repeated.

		cohesiveNodeStartNumber is used to dictate how much each node number is incremented for each duplicate found.
	"""
	print "Step7-1"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1

	##########################################################################################
	nodeSupport = [] #Global variable to store list of cohesive nodes that make up a cohesive face and elements in the damage zone attached to these nodes
	
	# Main function of this step
	nodeSupport = func3(elementList, cohesiveFaces)

	# Pickle cohesiveFaces for later use
	cohesiveFaces = pklObj(cohesiveFaces, pklFileName['cohesiveFaces'])

	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("Step7-1",time1,time2) 
	##########################################################################################
	##########################################################################################
	# Go through each affected node and modify that node number in each affected element so that the node numbers are unique
	print "Step7-2"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1

	tempNodeNode = [] #Global variable to store new nodes created as a result of node renumbering
	
	# Main function of this step
	tempNodeNode = func4(nodeSupport, elementList, elementListNumber, elementListIndex, cohesiveNodeStartNumber)

	# Pickle for later use
	elementList = pklObj(elementList, pklFileName['elementList'])

	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("Step7-2",time1,time2) 
	##########################################################################################
	##########################################################################################
	# Unpickle nodeList for use
	nodeList = unpklObj(pklFileName['nodeList'])

	# Go through each new node number that was changed and give back the (x,y,z) coordinates of the original node number. Then attach them to nodeList
	print "Step7-3"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1

	# Main function of this step
	func5(tempNodeNode, nodeList, nodeListNodeNumber, nodeListNodeIndex, cohesiveNodeStartNumber)
	
	# Resort node list for speed up on step 9
	[nodeListNodeNumber, nodeListNodeIndex] = sortIntColumnForBisectSearch(nodeList,0)

	# Pickle nodeList for later use
	nodeList = pklObj(nodeList, pklFileName['nodeList'])

	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("Step7-3",time1,time2) 
	##########################################################################################
	#____________________STEP 8______________________________
	# Fix the node number on damage elements
	print "Step8"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1

	# Unpickle elementList for use
	elementList = unpklObj(pklFileName['elementList'])

	# Unpickle elementListNormal for use
	elementListNormal = unpklObj(pklFileName['elementListNormal'])

	# Main function of this step
	func6(elementList, elementListNormal, elementListNormalNumber, elementListNormalIndex)

	# Pickle elementListNormal for later use
	elementListNormal = pklObj(elementListNormal, pklFileName['elementListNormal'])

	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("Step8",time1,time2) 
	#____________________STEP 9______________________________
	# Add the cohesive elements created to the cohesive list.
	print "Step9"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1

	# Unpickle nodeList for use
	nodeList = unpklObj(pklFileName['nodeList'])

	#making sure the nodeList are actually numbers
	for a in nodeList:
		a[0] = int(float(a[0]))
		a[1] = float(a[1])
		a[2] = float(a[2])
		a[3] = float(a[3])
	   
	time_intermediate = time.strftime("%d-%H-%M-%S", time.gmtime())
	savingTime("	Step9to9.1",time1,time_intermediate)

	# Pickle nodeList for use
	nodeList = pklObj(nodeList, pklFileName['nodeList'])

	# Unpickle elementList for use
	elementList = unpklObj(pklFileName['elementList'])

	# Unpickle cohesiveFaces for use
	cohesiveFaces = unpklObj(pklFileName['cohesiveFaces'])

	cohesive = []

	# Main function of this step
	cohesive = func7(cohesiveFaces, elementList, elementListNumber, elementListIndex, faceOrientation)


	#Finished using elementList. Print out results and clear variable for space.
	with open("%s/elementList-%s.txt" %(outputDirectory,inputName), 'w') as f:
		for k in elementList:
			f.writelines ("%s\n" %k)

	# Pickle elementList for debugging if needed
	elementList = pklObj(elementList,pklFileName['elementList'])

	# Pickle cohesiveFaces for debugging if needed
	cohesiveFaces = pklObj(cohesiveFaces,pklFileName['cohesiveFaces'])

	time_intermediate2 = time.strftime("%d-%H-%M-%S", time.gmtime())
	savingTime("	Step9.1to9.2",time_intermediate,time_intermediate2)

	#Create the element numbers for cohesive elements such that they are unique
	elementNumberCohesive = []
	rcount = cohesiveElementStartNumber	   
	for k in range (0, len(cohesive)):
		cohesive[k][0] = rcount
		elementNumberCohesive.append(cohesive[k][0])
		rcount=rcount+1

	#Saving Files
	with open("%s/cohesiveElement-%s.txt" %(outputDirectory,inputName), 'w') as f:
		for k in cohesive:
			f.writelines ("%s\n" %k)

	#Pickle cohesive for later use
	cohesive = pklObj(cohesive, pklFileName['cohesive'])
			
	#Pickle elementNumberCohesive for later use
	elementNumberCohesive = pklObj(elementNumberCohesive, pklFileName['elementNumberCohesive'])

	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("	Step9.2to10",time_intermediate2,time2)
	savingTime("Step9",time1,time2)

	#____________________STEP 10______________________________
	print "10"
	time1= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time1
			
	###################################################################
					
	#Write new inp file
	with open("%s/OutPut-%s.inp" %(outputDirectory,inputName), 'w') as f:
		
		#Copy the header into the file
		copyFromFileLineNumber(inputFile,f,1,nodeStart)

		# Unpickle nodeList and write to file
		nodeList = unpklObj(pklFileName['nodeList'])
		f.writelines(nodeStartInp+"\n")
		for k in nodeList:
			f.writelines(','.join(str(v) for v in k)+"\n")

		# Clear out nodeList
		nodeList = []

		# Unpickle elementListNormal and write to file
		elementListNormal = unpklObj(pklFileName['elementListNormal'])
		f.writelines(elementNormalStartInp+"\n")
		for s in elementListNormal:
			f.writelines(','.join(str(h) for h in s)+"\n")
		
		# Clear out elementListNormal
		elementListNormal = []

		# Copy everything after the element list up to the end of the damage regiion section
		copyFromFileLineNumber(inputFile,f,elementNormalEnd,elementDamageEnd)

		# Unpickle cohesive amd write to file
		cohesive = unpklObj(pklFileName['cohesive'])
		f.writelines(cohesiveTitle)
		for r in cohesive:
			f.writelines(','.join(str(h) for h in r)+"\n")
		
		# Clear out cohesive
		cohesive = []

		# Unpickle elementNumberCohesive and write to file
		elementNumberCohesive = unpklObj(pklFileName['elementNumberCohesive'])
		f.writelines(elementSetCohesive)
		f.writelines("%s,%s, \n"% (str (elementNumberCohesive[0]), str(elementNumberCohesive[-1])))
		f.writelines(sectionCohesive)

		# Clear out elementNumberCohesive
		elementNumberCohesive = []

		# Copy the rest of the file
		copyFromFileLineNumber(inputFile,f,elementDamageEnd,endOfFileLineNumber(inputFile)+1)
			
	time2= time.strftime("%d-%H-%M-%S", time.gmtime())
	print time2
	print "##############################"
	savingTime("Step10",time1,time2)

	# Remove pickled objects from disk
	delFile(pklFileName['elementList'])
	delFile(pklFileName['elementListNormal'])
	delFile(pklFileName['nodeList'])
	delFile(pklFileName['elementNumbers'])
	delFile(pklFileName['cohesiveFaces'])
	delFile(pklFileName['elementNumberCohesive'])
	delFile(pklFileName['cohesive'])

if __name__ == '__main__':

	# Start of program when calling from command line.
	generateCohesiveElements()
