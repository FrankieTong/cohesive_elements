# README #

This README is a for the usage of the cohesive_element module. Check the `V17 SOP` documentation and the header documentation in `v17-x.py` for more details.

### How do I get set up? ###

This program was built using Python v2.9.7 on a UNIX based system due to how UNIX handles global variables between multiple processes as shared memory when used in a read only fashion.
Although the program will run on WINDOWS based computers, the global copy for processes on WINDOWS systems causes the program to run suboptimally.
It is suggested to run this program on UNIX based system when working with large ABAQUS files and only use WINDOWS for testing.

### Running the Program ###

The main program can be called directly from the command line using the following command:

`python v17-x.py`

##### Input Parameters #####

Input inp file with the name `input.inp` should be located in the folder `inp/input.inp` located in the same directory of the program. 
The variable `inputName` in the program `v17-x.py` should then be changed to `inputName = "input"` before running the program.
	
##### Outputs #####

A folder with the output inp file should be found in the `reports` folder in the same directory of the program.

### Who do I talk to? ###

Code Creator: Hammid Ebrahimi [hamid.ebrahimi@mail.utoronto.ca], Saied Samiezadeh [saeid.samiezadeh@ryerson.ca]

Code Maintainer: Frankie (Hoi-Ki) Tong [frankietong@hotmail.com]
