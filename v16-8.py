"""Inserts cohesive elements into a defined damage zone in bone.

This program takes an "inp" Abaqus file containing bone material and a defined damage zone
and inserts cohesive elements within the damage region. An "inp" file is then output with the
new cohesive element zone defined.

Example:
	Given document file with the name "input.inp" located in the folder "inp/input.inp", 
	change the inputName = "input" and run the python program from the command window.

		$ python v16-8.py
	
	Output will be found in "reports/<output file name>" in the directory where this program
	is run.
	
For more information on how to use this program, please refer to README.md and the SOP packaged
with this program.

This program is designed for use on LINUX based systems.

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
		topSectionStart (optional)(str): Line in input inp file that indicates the start of the beginning 
			section of the file.
		topSectionEnd (optional)(str): Line in input inp file that indicates the end of the beginning 
			section of the file.
		nodeStartInp (optional)(str): Line in input inp file that indicates the start of the node 
			section of the file.
		nodeEndInp (optional)(str): Line in input inp file that indicates the end of the node 
			section of the file.
		elementNormalStartInp (optional)(str): Line in input inp file that indicates the start of the element 
			section of the file.
		elementNormalEndInp (optional)(str): Line in input inp file that indicates the end of the element 
			section of the file.
		midSectionStart (optional)(str): Line in input inp file that indicates the start of the middle 
			section of the file.
		midSectionEnd (optional)(str): Line in input inp file that indicates the end of the middle 
			section of the file.
		elementDamageStartInp (optional)(str): Line in input inp file that indicates the start of the elements 
			in the damage region section of the file.
		elementDamageEndInp (optional)(str): Line in input inp file that indicates the end of the elements 
			in the damage region section of the file.
		endSectionStart (optional)(str): Line in input inp file that indicates the start of the end 
			section of the file.
		endSectionEnd (optional)(str): Line in input inp file that indicates the end of the end 
			section of the file.
			
"""
#YOU MUST CHANGE#####################################
inputName = "Rat_721_partial_w_dam_smal"

#YOU CAN CHANGE######################################
core = 8 

cohesiveElementStartNumber=10000000
cohesiveNodeStartNumber = 10000000

topSectionStart = "*Heading"
topSectionEnd = "*Node"

nodeStartInp="*Node"
nodeEndInp  = "*Element, type=C3D8"

elementNormalStartInp = "*Element, type=C3D8"
elementNormalEndInp =  "*Nset, nset=NODES-ELEMS, generate"

midSectionStart = "*Nset, nset=NODES-ELEMS, generate"
midSectionEnd = "*Solid Section, elset=BONE, material=BONE"

elementDamageStartInp = "*Elset, elset=DAMAGE"
elementDamageEndInp=    "*Elset, elset=BONE, generate"

endSectionStart = "*Solid Section, elset=BONE, material=BONE"
endSectionEnd = "*End Step"

#YOU SHOULD NOT #####################################
#_____________________________________
#Define input and output inp file names
inputFile= "inp/%s.inp"%inputName
outputFile = "%s-output.inp"%inputFile
#_____________________________________
#Module imports
import itertools
import collections
from itertools import groupby
import time
from time import gmtime, strftime
import os
from datetime import datetime
import multiprocessing as mp
import copy
import bisect
import sys
#_____________________________________

# General support functions used throughout the program
def savingTime(step,timeStart,timeEnd):
	"""Writes time elasped by appending to a file.
			
	Args:
		step (str): Tag for the current time being saved.
		timeStart (str): gmtime object with the format defined in FMT generated with the starting time.
		timeStop (str): gmtime object with the format defined in FMT generated with the ending time.

	The function will attempt to open a file found in "<directory>/time-<inputName>.txt" where
	<directory> and <inputName> are global variables.
	
	Format of gmtime() object given as an input is defined individually across multiple areas in the script.
		
	"""
    FMT = '%d-%H-%M-%S'
    difference = datetime.strptime(timeEnd,FMT)-datetime.strptime(timeStart,FMT)
    with open("%s/time-%s.txt" %(directory,inputName), 'a') as f:
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
    return sortedListIndex[index]
    
# Main program
#____________________STEP 0______________________________
""" Create the results folder where results will be stored.

"""
stamp = strftime("%Y-%m-%d %H-%M-%S", gmtime())
directory = "reports/%s-%s" %(inputName,stamp)
if not os.path.exists(directory):
    os.makedirs(directory)
#____________________STEP 1______________________________
""" Read in the inp file and store into memory.

	TODO: Read and write to/from file directly rather than storing all of it in memory to deal with large files.

"""

print "Step1"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

with open(inputFile) as file:
    data = file.readlines()
time2= strftime("%d-%H-%M-%S", gmtime())

print time2
print "##############################"
savingTime("Step1",time1,time2)
#____________________STEP 2______________________________
""" Identify the individual sections of the files and store their starting and ending line numbers. Stop script if any section is not clearly defined.

"""
print "Step2"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

#Preassign line numbers to each header and ending to identify if a section is incomplete
topSectionStartLine = -1
topSectionEndLine = -1
midSectionStartLine = -1
midSectionEndLine = -1
endSectionStartLine = -1
endSectionEndLine = -1
nodeStart = -1
nodeEnd = -1
elementStart = -1
elementEnd = -1
elementNormalStart = -1
elementNormalEnd = -1

#Go through the stored lines and find the line number each header/ending could be found

#mark the top section of the file:
for i in range (0, len(data)):
    if data[i].strip() == topSectionStart:
        topSectionStartLine = i

    if data[i].strip() == topSectionEnd:
        topSectionEndLine = i
        
#mark the mid section of the file:
for i in range (0, len(data)):
    if data[i].strip() == midSectionStart:
        midSectionStartLine = i

    if data[i].strip() == midSectionEnd:
        midSectionEndLine = i

#mark the end section of the file:
for i in range (0, len(data)):
    if data[i].strip() == endSectionStart:
        endSectionStartLine = i

    if data[i].strip() == endSectionEnd:
        endSectionEndLine = i

#mark the start of nodes
for i in range (0, len(data)):
    if data[i].strip() == nodeStartInp:
        nodeStart = i+1

    if data[i].strip() == nodeEndInp:
        nodeEnd = i
        
#marking the start and end of Damage elements
for j in range (0, len(data)):
    if data[j].strip() == elementDamageStartInp:
        elementStart = j+1

    if data[j].strip() == elementDamageEndInp:
        elementEnd = j

#marking the start and end of Normal elements
for j in range (0, len(data)):
    if data[j].strip() == elementNormalStartInp:
        elementNormalStart = j+1

    if data[j].strip() == elementNormalEndInp:
        elementNormalEnd = j

#If any one of these sections are not clearly defined. Print out line numbers and stop the program.
if (topSectionStartLine < 0 or topSectionEndLine < 0 or midSectionStartLine < 0 or midSectionEndLine < 0 or endSectionStartLine < 0 or \
endSectionEndLine < 0 or nodeStart < 0 or nodeEnd < 0 or elementStart < 0 or elementEnd < 0 or elementNormalStart < 0 or elementNormalEnd < 0):
    print "One or more section(s) is/are missing. Line number of each sections found are:"
    print "topSection = "+str(topSectionStartLine)+" to "+str(topSectionEndLine)
    print "midSection = "+str(midSectionStartLine)+" to "+str(midSectionEndLine)
    print "endSection = "+str(endSectionStartLine)+" to "+str(endSectionEndLine)
    print "node = "+str(nodeStart)+" to "+str(nodeEnd)
    print "elementDamage = "+str(elementStart)+" to "+str(elementEnd)
    print "elementNormal = "+str(elementNormalStart)+" to "+str(elementNormalEnd)

    sys.exit()

time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "##############################"
savingTime("Step2",time1,time2)
#____________________STEP 3______________________________
""" Parsing and storing the nodes, elements and damage elements into lists for easy access. 

"""
print "Step3"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

#storing nodes
nodeList = []
for l in range (nodeStart, nodeEnd):
    d = data[l].strip().split(",")
    nodeList.append(d)  

#getting rid of the extra space in the list
for z in range (0, len(nodeList)):
    for k in range (0,4):
        nodeList[z][k] = nodeList[z][k].strip()

# Sort nodeList to make searching quicker (for safe measure)
nodeListNodeNumber = []
nodeListNodeIndex = []
[nodeListNodeNumber, nodeListNodeIndex] = sortIntColumnForBisectSearch(nodeList,0)

##############################################
#storing Damage elments
temp = []
for s in range (elementStart, elementEnd):
    r = data[s].strip().split(",")
    temp = r + temp 

#getting rid of empty entry
elementNumbers = filter(None, temp)

#getting rid of the extra space in the list
for z in range (0, len(elementNumbers)):
    elementNumbers[z] = int(elementNumbers[z].strip())

##############################################
#storing Normal elments
elementListNormal = []
for s in range (elementNormalStart, elementNormalEnd):
    r = data[s].strip().split(",")
    elementListNormal.append(r)

#getting rid of the extra space in the list
for z in range (0, len(elementListNormal)):
    for k in range (0,9):
        elementListNormal[z][k] = int(elementListNormal[z][k].strip())

# Sort elementListNormal by node number to prepare for binary search later on in the program
elementListNormalNumber = []
elementListNormalIndex = []
[elementListNormalNumber, elementListNormalIndex] = sortIntColumnForBisectSearch(elementListNormal,0)		

time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "##############################"
savingTime("Step3",time1,time2)
#____________________STEP 4______________________________
""" For each element in the damage zone, grab the element and its nodes and add them to elementList for processing.

"""

print "Step4"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

##########################################################################################
# Grab the damanged elements and their neighbouring nodes from the list of all elements and store them in elementList

elementList = []	#Global variable to store elements in the damage zone

# Support functions for multiprocessing for this step
def log_result(result):
	"""Appends the resulting element found by the process to the global variable elementList
			
	Args:
		result (list): Element number and its defining nodes to be appended to elementList
		
	elementList is a global variable that is used to store the elements and their defining nodes in the damange zone.
	
	"""
	#Just a check to make sure we don't add blank elements. Should have an element to append everytime a process finishes.
    if result != None:
        elementList.append(result)

def check(element):
	"""Fuction processed by individual processes to search for an element from the enitre list of elements.
			
	Args:
		element (string): String containing the number of the element we want to search for in elementListNormal.
		
	Returns:
		elementListNormalNode (list): Found element and its defining nodes. Will return wrong element if element being searched does not exist.
		
	elementListNormal is a global variable that each process searches through to find the element they are searching for.
	
	"""

    # Search for the element and its defining nodes from sorted list using bisect search
    elementNumber = int(element)
    index = bisectSearchSortedList(elementNumber, elementListNormalNumber, elementListNormalIndex)
    elementListNormalNode = elementListNormal[index]

	# Check to make sure the element retireved is the one we want (search can fail if element does not exist in elementListNormal)
    if elementListNormalNode[0] == elementNumber:
        return elementListNormalNode

def func():
	"""Fuction to set up the multiprocess procedure to get elements in the damage zone from list of normal elements.
		
	elementNumbers is a global variable containing the list of element numbers in the damage zone.
	
	"""
	#Retrieve the elements and their defining nodes given element numbers defined in elementNumbers. Store result in elementList
    pool = mp.Pool(processes=core)
    for k in elementNumbers:
        pool.apply_async(check,(k,),callback = log_result)
    pool.close()
    pool.join()

# Main function of this step
#if __name__ == '__main__':
func()	

# Sort elementList by node number to prepare for binary search later on in the program
elementListNumber = []
elementListIndex = []
[elementListNumber, elementListIndex] = sortIntColumnForBisectSearch(elementList,0)

##########################################################################################
time2= strftime("%d-%H-%M-%S", gmtime())
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
time1= strftime("%d-%H-%M-%S", gmtime())
print time1
##########################################################################################
# For every damage element, check if the forward facing faces are connected to another damanged element. If it is, then add it to the list.
cohesiveFaces = [] 	#Global variable to store element number and cohesive face node for each connecting element in the damage zone

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

# Sort elementList by forward face orientation to prepare for binary search

# Combination A
elementListFaceANumber = []
elementListFaceAIndex = []
faceA = [5,6,7,8]
faceZ = [1,2,3,4]
[elementListFaceANumber, elementListFaceAIndex] = sortElementListForFaceBisectSearch(elementList,faceA)

# Combination B
elementListFaceBNumber = []
elementListFaceBIndex = []
faceB = [3,4,8,7]
faceY = [2,1,5,6]
[elementListFaceBNumber, elementListFaceBIndex] = sortElementListForFaceBisectSearch(elementList,faceB)

# Combination C
elementListFaceCNumber = []
elementListFaceCIndex = []
faceC = [2,3,7,6]
faceX = [1,4,8,5]
[elementListFaceCNumber, elementListFaceCIndex] = sortElementListForFaceBisectSearch(elementList,faceC)

# Support functions for multiprocessing for this step
def log_result2(cohesiveFacesList):
	"""Appends the resulting elements and cohesive face nodes found by the process to the global variable cohesiveFaces
			
	Args:
		cohesiveFacesList (list): Element number and its defining cohesive face nodes to be appended to cohesiveFaces
		
	cohesiveFaces is a global variable that is used to store the elements and their cohesive face nodes.
	
	"""
    cohesiveFaces.extend(cohesiveFacesList)

def check2(elem):
	"""Fuction processed by individual processes to search for cohesive faces from list of elements in the damage zone.
			
	Args:
		elem (string): String containing the element in the damage zone we want to search faces for.
		
	Returns:
		cohesiveFacesList (list): Found element, its connected element, and the shared cohesive face nodes. 
			Will return wrong elements if element being searched does not exist.
	
	"""
    
    cohesiveFacesList = []

    #combination A:
	#Search for faceZ combination from sorted elementList in conbimation A
    face = [elem[faceZ[0]],elem[faceZ[1]],elem[faceZ[2]],elem[faceZ[3]]]
    index = bisectSearchSortedList(face, elementListFaceANumber, elementListFaceAIndex)
    elementListNode = elementList[index]

    if face == [elementListNode[faceA[0]],elementListNode[faceA[1]],elementListNode[faceA[2]],elementListNode[faceA[3]]]:
        sortedFace = sorted(face)
        cohesiveFacesList.append([elementListNode[0], elem[0]] + sortedFace)
        cohesiveFacesList.append([elem[0], elementListNode[0]]  + sortedFace)
            
    #combination B:
	#Search for faceY combination from sorted elementList in conbimation B
    face = [elem[faceY[0]],elem[faceY[1]],elem[faceY[2]],elem[faceY[3]]]
    index = bisectSearchSortedList(face, elementListFaceBNumber, elementListFaceBIndex)
    elementListNode = elementList[index]

    if face == [elementListNode[faceB[0]],elementListNode[faceB[1]],elementListNode[faceB[2]],elementListNode[faceB[3]]]:
        sortedFace = sorted(face)
        cohesiveFacesList.append([elementListNode[0], elem[0]] + sortedFace)
        cohesiveFacesList.append([elem[0], elementListNode[0]]  + sortedFace)

    #combination C:
	#Search for faceX combination from sorted elementList in conbimation C
    face = [elem[faceX[0]],elem[faceX[1]],elem[faceX[2]],elem[faceX[3]]]
    index = bisectSearchSortedList(face, elementListFaceCNumber, elementListFaceCIndex)
    elementListNode = elementList[index]

    if face == [elementListNode[faceC[0]],elementListNode[faceC[1]],elementListNode[faceC[2]],elementListNode[faceC[3]]]:
        sortedFace = sorted(face)
        cohesiveFacesList.append([elementListNode[0], elem[0]] + sortedFace)
        cohesiveFacesList.append([elem[0], elementListNode[0]]  + sortedFace)
    
    #Should never go here
    return cohesiveFacesList

def func2():
	"""Fuction to set up the multiprocess procedure to find cohesive faces from elements in the damange zone.
		
	elementList is a global variable containing the list of element in the damage zone.
	
	"""
    pool2 = mp.Pool(processes=core)
    for elem in elementList:
        pool2.apply_async(check2,(elem,), callback = log_result2)
    pool2.close()
    pool2.join()

# Main function of this step
func2()

#Clean up of global variables that have no use anymore
elementListFaceANumber = []
elementListFaceAIndex = []
faceA = []
faceZ = []

elementListFaceBNumber = []
elementListFaceBIndex = []
faceB = []
faceY = []

elementListFaceCNumber = []
elementListFaceCIndex = []
faceC = []
faceX = []

# Information reordering to grab only the cohesive element and their face nodes. Also removes duplicates (if any)
unique = [([col[0]] + col[2:]) for col in cohesiveFaces]
cohesiveFaces = []

# Sort so that the pair faces sit next to each other 
s = sorted(unique, key = lambda x: (x[1],x[2],x[3],x[4]))
unique = []

#saving the pairNodes
with open("%s/pairNodes-%s.txt" %(directory,inputName), 'w') as f:
    for k in s:
        f.writelines ("%s\n" %k)

##########################################################################################
time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "############################"
savingTime("Step5and6",time1,time2)  

#____________________STEP 7______________________________  
""" Renumber each node in each element attached to a cohesive face so that the node numbers are not repeated.

	cohesiveNodeStartNumber is used to dictate how much each node number is incremented for each duplicate found.
"""
print "Step7-1"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

##########################################################################################
nodeSupport= []	#Global variable to store list of cohesive nodes that make up a cohesive face and elements in the damage zone attached to these nodes
addNodeSupport = []	#Global variable to store which nodes are connected to which damage elements

#Make sorted list of all unique nodes that are a member of a cohesive face
cohesiveFaceNodeUnique = []	#Global variable to store unique nodes that are connected to cohesive faces

#Make a list of all unique nodes that make up of cohesive faces and sort them
cohesiveFaceNodeUnique = map(lambda x: x[1:], s)
cohesiveFaceNodeUnique = list(set(int(i) for j in cohesiveFaceNodeUnique for i in j))
cohesiveFaceNodeUnique.sort()

nodeSupport = [[i] for i in cohesiveFaceNodeUnique]	#Global variable to store all cohesive nodes and cohesive elements attached to those nodes

# Support functions for multiprocessing for this step
def log_result3(support):
	"""Appends the changes need to be made to addNodeSupport
			
	Args:
		the (list): 2D list of index numbers and element numbers to be added to nodeSupport
		
	addNodeSupport is a global variable that is used to store the changes to be made to nodeSupport
	
	"""
    if support != None:
        addNodeSupport.extend(support)

def check3(elem):
	"""Fuction processed by individual processes to search each node found in each element in the damage zone to see which nodes make up of cohesive faces.
			
	Args:
		elem (list): Element and nodes defining the element to be searched for cohesive face node numbers.
		
	Returns:
		support (list): 2D list of index numbers and element numbers to be added to nodeSupport
		
	cohesiveFaceNodeUnique is a global variable that each process searches through.
	
	"""
    support = []
    checkNodes = elem[1:]

    for i in checkNodes:
        index = bisect.bisect_left(cohesiveFaceNodeUnique, i)
        if cohesiveFaceNodeUnique[index] == i:
            support.append([index, elem[0]])
    return support

def func3():
	"""Fuction to set up the multiprocess procedure to find each element in the damage zone that connects with an affected node.
		
	elementList is a global variable containing the list of element numbers in the damage zone.
	addNodeSupport is a global variable that contains all the changes needed to be made to nodeSupport
	
	"""
    pool2 = mp.Pool(processes=core)

    #Go through elementList and check if any of the nodes lie in the unqiue list of nodes in the list of cohesive faces. For each that appear, insert to support.
    for elem in elementList:
        pool2.apply_async(check3,(elem,),callback = log_result3)
    pool2.close()
    pool2.join()

    for i in addNodeSupport:
        nodeSupport[i[0]].extend([i[1]])

# Main function of this step
func3()

# Clean up of variables 
cohesiveFaceNodeUnique = []
addNodeSupport = []

time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "##############################"
savingTime("Step7-1",time1,time2) 
##########################################################################################
##########################################################################################
# Go through each affected node and modify that node number in each affected element so that the node numbers are unique
print "Step7-2"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

tempNodeNode = [] #Global variable to store new nodes created as a result of node renumbering
fixElementNode = [] #Global variable to store changes to elements that need to have their node numbers fixed

def log_result4(tempNodeAndFixElementNode):
	"""Appends the changes to be made to elementList and new nodes created to list of global variables
			
	Args:
		tempNodeAndFixElementNode (list): Element number and node that needs to be fixed as well as new nodes to be added to the nodeList
		
	tempNodeNode is a global variable that contains the new node numbers that were created
	fixElementNode contains the index number and changes to be made to the node number in that element
	
	"""
    tempNodeNode.append(tempNodeAndFixElementNode[0])
    fixElementNode.extend(tempNodeAndFixElementNode[1])

def check4(n):#n=[nodenumber, element1, element2, element3, ..., element8] It may only be two elements
	"""Fuction processed by individual processes to search for elements attached to each cohesive face node.
			
	Args:
		n (string): Node number and list of elements attached to the node.
		
	Returns:
		[tempNode, fixNode] (list): lement number and node that needs to be fixed as well as new nodes to be added to the nodeList
		
	elementList is a global variable that each process searches through to find the element they are searching for.
	
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
                if  n[0] == elementListNode[k]:
                    # Store changes to be made into queue for editing elementList at main program
                    fixNodeNumber = [index,k,(n[0] + increase)]
                    fixNode.append(fixNodeNumber)
                    tempNode.append(n[0]+increase)
            increase = increase + cohesiveNodeStartNumber
    return [tempNode, fixNode]
                   

def func4():
	"""Fuction to set up the multiprocess procedure to renumber repeated nodes that make up of cohesive faces
		
	nodeSupport is a global variable containing the list of nodes and affected elements that need to be modified.
	
	fixElementNode is a global variable used to store changes to be made to global variable elementList made the each process.
	
	"""
    temptemp = []
    counterFinal=0
    pool2 = mp.Pool(processes=core)
    
    for a in nodeSupport:
        pool2.apply_async(check4,args=(a,),callback = log_result4)
        print len(nodeSupport)-counterFinal
        counterFinal=counterFinal+1
    pool2.close()
    pool2.join()
    
    #Write changes marked by the processes into elementList
    for fixNode in fixElementNode:
        elementList[fixNode[0]][fixNode[1]] = fixNode[2]

# Main function of this step
func4()

time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "##############################"
savingTime("Step7-2",time1,time2) 
##########################################################################################
##########################################################################################
# Go through each new node number that was changed and give back the (x,y,z) coordinates of the original node number. Then attach them to nodeList

print "Step7-3"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

# Empty array to store newly created node numbers and their coordinates
nodeListTemp = []

def log_result5(re):
	"""Appends the new nodes and their coordinates to a nodeListTemp
			
	Args:
		re (list): New node numbers and their coordinates
		
	nodeListTemp is a global variable that is used to temporary store the new nodes.
	
	"""
    nodeListTemp.append(re)

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

def func5():
	"""Fuction to set up the multiprocess procedure to get create new node entries for the newly created nodes.
		
	tempNodeNode is a global variable containing the list of nodes numbers to be added to nodeList.
	
	"""
    counterFinal2=0
    pool2 = mp.Pool(processes=core)
    for a in tempNodeNode:
        print len(tempNodeNode)-counterFinal2
        counterFinal2=counterFinal2+1
        for r in a:
            pool2.apply_async(check5,(r,),callback = log_result5)
    pool2.close()
    pool2.join()

    # Add the newly create node numbers and their coordinates into the nodeList
    nodeList.extend(nodeListTemp)

# Main function of this step
func5()

# Resort node list for speed up on step 9
[nodeListNodeNumber, nodeListNodeIndex] = sortIntColumnForBisectSearch(nodeList,0)

time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "##############################"
savingTime("Step7-3",time1,time2) 
##########################################################################################
#____________________STEP 8______________________________
# Fix the node number on damage elements
print "Step8"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

fixElementListNormal = [] #Global variable to store the changed needed to be made to elementListNormal

# Support functions for multiprocessing for this step
def log_result6(result):
	"""Appends the fixes needed to be made to elementListNormal to fixElementListNormal
			
	Args:
		result (list): Element number and its defining nodes to be fixed in elementListNormal
		
	fixElementListNormal is a global variable that is used to store the fixes to elementListNormal.
	
	"""
    fixElementListNormal.append(result)

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


def func6():
	"""Fuction to set up the multiprocess procedure to find and modify elements in the normal element list to add cohesive elements.
		
	elementList is a global variable containing the list of damage element with the modified node numbers.
	
	fixElementListNormal is a global variable containing the changed needed to be made to elementListNormal.
	
	"""
    pool2 = mp.Pool(processes=core)
    for elementListNode in elementList:
        pool2.apply_async(check6,(elementListNode,),callback=log_result6)
    pool2.close()
    pool2.join()

    # Apply the changes found in node ordering to cohseive nodes
    for i in fixElementListNormal:
        elementListNormal[i[0]] = i[1]

# Main function of this step
func6()

# Clean up of variables
fixElementListNormal = []

time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "##############################"
savingTime("Step8",time1,time2) 
#____________________STEP 9______________________________
# Add the cohesive elements created to the cohesive list.
print "Step9"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

#making sure the nodeList are actually numbers
for a in nodeList:
    a[0] = int(float(a[0]))
    a[1] = float(a[1])
    a[2] = float(a[2])
    a[3] = float(a[3])
   
time_intermediate = strftime("%d-%H-%M-%S", gmtime())

#create cohesive elements
counterCohesive = 0
cohesive= []
cohesive.append([])
d = 0 
for l in s:

	# Find the element attached to each side of each cohesive face from elementList and fix their node numbers before adding them to the cohesive list
    index = bisectSearchSortedList(l[0], elementListNumber, elementListIndex)
    elementListNode = elementList[index]

    if l[0] == elementListNode[0]:              #if the element numbers were the same
        for j in elementListNode[1:]:           #grab all nodes of the current element
            
            if j < cohesiveNodeStartNumber:
                if j in l[1:]:
                        cohesive[d].append(j)
                        
            if cohesiveNodeStartNumber < j < 2*cohesiveNodeStartNumber:
                    tmp = j - cohesiveNodeStartNumber
                    if tmp in l[1:]:
                        cohesive[d].append(j)
        
            if 2*cohesiveNodeStartNumber < j < 3*cohesiveNodeStartNumber:
                    tmp = j - 2*cohesiveNodeStartNumber
                    if tmp in l[1:]:
                        cohesive[d].append(j)

            if 3*cohesiveNodeStartNumber < j < 4*cohesiveNodeStartNumber:
                    tmp = j - 3*cohesiveNodeStartNumber
                    if tmp in l[1:]:
                        cohesive[d].append(j)

            if 4*cohesiveNodeStartNumber < j < 5*cohesiveNodeStartNumber:
                    tmp = j - 4*cohesiveNodeStartNumber
                    if tmp in l[1:]:
                        cohesive[d].append(j)

            if 5*cohesiveNodeStartNumber < j < 6*cohesiveNodeStartNumber:
                    tmp = j - 5*cohesiveNodeStartNumber
                    if tmp in l[1:]:
                        cohesive[d].append(j)

            if 6*cohesiveNodeStartNumber < j < 7*cohesiveNodeStartNumber:
                    tmp = j - 6*cohesiveNodeStartNumber
                    if tmp in l[1:]:
                        cohesive[d].append(j)

            if 7*cohesiveNodeStartNumber < j < 8*cohesiveNodeStartNumber:
                    tmp = j - 7*cohesiveNodeStartNumber
                    if tmp in l[1:]:
                        cohesive[d].append(j)
                        
        counterCohesive +=1
        if counterCohesive % 2 == 0:
            d +=1
            cohesive.append([])

cohesive.pop() # removes the last emepty entry

time_intermediate2 = strftime("%d-%H-%M-%S", gmtime())

#Modify the element numbers for cohesive elements such that they are unique
elementNumberCohesive = []
rcount = cohesiveElementStartNumber    
for k in range (0, len(cohesive)):
    cohesive[k] = [rcount] + cohesive[k]
    elementNumberCohesive.append(cohesive[k][0])
    rcount=rcount+1

time_intermediate3 = strftime("%d-%H-%M-%S", gmtime())

# Reorder the node numbers in cohesive to match the convention set by Abaqus
fixCohesive = [] 	# Global variable containing an empty array to store changes to be made to fix the node orders in cohesiveElements

# Support functions for multiprocessing for this step
# Store changes to be made in node ordering of cohesive nodes in a temporary array
def log_result7(result):
	"""Appends the changes to be made to elements in cohesive to fixCohesive
			
	Args:
		result (list): Cohesive node index and their new node number ordering.
		
	fixCohesive is a global variable that stores the changes to be made.
	
	"""
    fixCohesive.append(result)

# Go through each cohesive node and check if changes to node ordering need to be made
def check7(cohesiveNodeIndex, cohesiveNode):
	"""Fuction processed by individual processes to search for reodering the node numbering in each cohesive element.
			
	Args:
		cohesiveNodeIndex (int): Index of current cohesive node being fixed.
		cohesiveNode (list): Element number and its defining nodes for the cohesive element being fixed.
		
	Returns:
		[cohesiveNodeIndex,cohesiveNode] (list): Current cohesive element index number and its reordered node ordering.
	
	"""
    flag = []

    temp1x=1;temp1y=2;temp1z=3;temp2x=4;temp2y=5;temp2z=6;temp3x=7;temp3y=8;temp3z=9
    #first 4 nodes: do they have the same x, y or z coordinate, if they are the same x then dont do anything, for y and z
    #you already know one and you need to figure out a algorithm to deal with the last one

    searchNode = cohesiveNode[1]
    index = bisectSearchSortedList(searchNode, nodeListNodeNumber, nodeListNodeIndex)
    nodeListNode = nodeList[index]

    if nodeListNode[0] == searchNode:
        temp1x = nodeListNode[1]
        temp1y = nodeListNode[2]
        temp1z = nodeListNode[3]

    searchNode = cohesiveNode[2]
    index = bisectSearchSortedList(searchNode, nodeListNodeNumber, nodeListNodeIndex)
    nodeListNode = nodeList[index]

    if nodeListNode[0] == searchNode:
        temp2x = nodeListNode[1]
        temp2y = nodeListNode[2]
        temp2z = nodeListNode[3]

    searchNode = cohesiveNode[3]
    index = bisectSearchSortedList(searchNode, nodeListNodeNumber, nodeListNodeIndex)
    nodeListNode = nodeList[index]

    if nodeListNode[0] == searchNode:
        temp3x = nodeListNode[1]
        temp3y = nodeListNode[2]
        temp3z = nodeListNode[3]

    searchNode = cohesiveNode[4]
    index = bisectSearchSortedList(searchNode, nodeListNodeNumber, nodeListNodeIndex)
    nodeListNode = nodeList[index]

    if nodeListNode[0] == searchNode:
        temp4x = nodeListNode[1]
        temp4y = nodeListNode[2]
        temp4z = nodeListNode[3]

    if temp1x==temp2x and temp2x==temp3x and temp3x==temp4x:
        flag.append("A")

        cohesiveNode[3],cohesiveNode[4] = cohesiveNode[4], cohesiveNode[3]
        cohesiveNode[7],cohesiveNode[8] = cohesiveNode[8], cohesiveNode[7]
    
    elif temp1y==temp2y and temp2y==temp3y and temp3y==temp4y:
        flag.append("B")

        cohesiveNode[1],cohesiveNode[2] = cohesiveNode[2], cohesiveNode[1]
        cohesiveNode[7],cohesiveNode[8] = cohesiveNode[8], cohesiveNode[7]

    elif temp1z==temp2z and temp2z==temp3z and temp3z==temp4z:
        flag.append("C")
        #Do nothing 

    return [cohesiveNodeIndex,cohesiveNode]

def func7():
	"""Fuction to set up the multiprocess procedure to fix the node ordering of the cohesive nodes.
		
	cohesive is a global variable containing the list of cohesive elements to be fixed.
	
	"""
    pool2 = mp.Pool(processes=core)
    for cohesiveNodeIndex in range(0,len(cohesive)):
        pool2.apply_async(check7,(cohesiveNodeIndex,cohesive[cohesiveNodeIndex]),callback = log_result7)
    pool2.close()
    pool2.join()

    # Apply the changes found in node ordering to cohseive nodes
    for i in fixCohesive:
        cohesive[i[0]] = i[1]
		
# Main function of this step
func7()

# Clean up of variables
fixCohesive = []

time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "##############################"
savingTime("Step9",time1,time2)
savingTime("    Step9to9.1",time1,time_intermediate)
savingTime("    Step9.1to9.2",time_intermediate,time_intermediate2)
savingTime("    Step9.2to9.3",time_intermediate2,time_intermediate3)
savingTime("    Step9.3to10",time_intermediate3,time2)

#____________________STEP 10______________________________
# Create the new inp file with the cohesive elements added in the damage zone.

print "10"
time1= strftime("%d-%H-%M-%S", gmtime())
print time1

#Saving Files
with open("%s/cohesiveElement-%s.txt" %(directory,inputName), 'w') as f:
    for k in cohesive:
        f.writelines ("%s\n" %k)
        
with open("%s/elementList-%s.txt" %(directory,inputName), 'w') as f:
    for k in elementList:
        f.writelines ("%s\n" %k)
                         
###################################################################
elements = "*Element, type=C3D8\n"
cohesiveTitle = "*Element, type=COH3D8\n"
elementSetCohesive = "*Elset, elset=COH_ELEM_SET, generate\n"
sectionCohesive = "** Section: Section-2-COH\n\
*Cohesive Section, elset=COH_ELEM_SET, material=DAMAGE, response=TRACTION SEPARATION\n"

with open("%s/OutPut-%s.inp" %(directory,inputName), 'w') as f:

    for i in data[topSectionStartLine:topSectionEndLine+1]:
        f.writelines(i)
        
    for k in nodeList:
        f.writelines(','.join(str(v) for v in k)+"\n")

    f.writelines(elements)
    for s in elementListNormal:
        f.writelines(','.join(str(h) for h in s)+"\n")

    for i in data[midSectionStartLine:midSectionEndLine+1]:
        f.writelines(i)    
    
    f.writelines(cohesiveTitle)
    for r in cohesive:
        f.writelines(','.join(str(h) for h in r)+"\n")
    
    f.writelines(elementSetCohesive)
    f.writelines("%s,%s, \n"% (str (elementNumberCohesive[0]), str(elementNumberCohesive[-1])))
    f.writelines(sectionCohesive)

    for i in data[endSectionStartLine:endSectionEndLine+1]:
        f.writelines(i)
        
		
time2= strftime("%d-%H-%M-%S", gmtime())
print time2
print "##############################"
savingTime("Step10",time1,time2)

