P3 — Fermentation Kinetics from Batch Data
Kinetic modelling and parameter estimation
Eight lab-scale batch fermentations on molasses medium are provided. Develop a kinetic model from these
data, establish what the data can and cannot determine, and use the model to recommend operating
conditions for the plant.
Tool: Python or MATLAB. Write the model equations yourself; any solver library is fine.
1. THE SITUATION
During October, the plant cannot hold its fermenters below 33 °C at peak load. The production manager wants
to know which initial sugar concentration and fermentation temperature to use, and whether a stronger wash
would be worthwhile. To support this decision, the R&D lab carried out eight batch runs in 5 L fermenters. Your
recommendation should be quantitative and should state its uncertainty.
2. WHAT YOU ARE MODELLING
In a batch fermentation, yeast grows on the sugars in diluted molasses and converts them to ethanol and CO2 ,
with small amounts of by-products such as glycerol. Growth and ethanol production slow down as conditions
in the broth change during the batch. A kinetic model describes these rates as a set of ordinary differential
equations for biomass, sugar and ethanol (and any other species you choose to include), and its parameters
are estimated by fitting the model to the measured data. The form of the rate expressions, the parameters, and
how they depend on temperature are for you to decide.
3. YOUR DATASET
Download P3_dataset.zip using the link in section 3 of the overview. It contains three files.
File
runs.csv
timecourse.csv
Column
run
temperature_C
initial_TRS_g_L_as_glucose
initial_sugars_sucrose_plus_reducing_g_L
inoculum_biomass_g_L
notes
time_h
biomass_g_L
Meaning (unit)
Run identifier, R1 to R8
Fermentation temperature, held constant (°C)
Sugar at the start, as total reducing sugars
expressed as glucose (g/L)
The same sugar charge reported as sucrose plus
reducing sugars, by mass, before inversion (g/L)
Yeast added at the start (g/L, dry weight)
Remarks from the lab
Time since inoculation (h): 0, 2, 4, 6, 8, 10, 12, 16,
20, 24, 30, 36, 42 and 48
Yeast biomass (g/L, dry weight)
TRS_g_L_as_glucose
ethanol_g_L
CO2_evolved_g_per_L
Remaining sugar as total reducing sugars,
expressed as glucose (g/L)
Ethanol (g/L)
Cumulative CO2 released since inoculation, per litre
of broth (g/L)
CHEMICAL PROCESS · 13
File
endpoint_hplc.csv
Column
glycerol_g_L, lactic_acid_g_L
Meaning (unit)
By-products at 48 h (g/L); “n.d.” means not
detected (below 0.2 g/L)
final_pH
pH of the broth at 48 h
Measurement
Biomass
Sugar (TRS)
Ethanol
CO2 evolved
Glycerol, lactic acid
pH
Method
Dry cell weight, unless the run notes say otherwise
HPLC
Typical uncertainty (one standard
deviation)
±(3.5% + 0.08 g/L)
Total reducing sugars after acid inversion, as glucose
Off-gas mass flow, integrated over time
HPLC at 48 h
pH meter at 48 h
±(1% + 0.4 g/L)
±(1.2% + 0.25 g/L)
About ±2%
About ±3%
±0.04
Assume the broth volume stays constant, and that ethanol carried off with the CO2 is condensed and returned.
Species
Glucose
Sucrose
Ethanol
Carbon dioxide
Glycerol
Lactic acid
Formula
C6H12O6
C12H22O11
C2H6O
CO2
Molar mass (g/mol)
180.16
342.30
46.07
44.01
C3H8O3
C3H6O3
Yeast biomass
CH1.8O0.5N0.2
4. PLANT DATA (NEEDED FOR LEVEL 3 ONLY)
92.09
90.08
24.6 per C-mol
Item
Fermenter working volume
Turnaround between batches (empty, clean, refill)
Highest allowed sugar left at the end of a batch
Lowest temperature the plant can hold at peak load
Fuel ethanol price
Fermentable sugar cost
LP steam
Value
170 m3
8 h
5 g/L TRS
33 °C now; 36 °C if the cooling water warms by 3 °C
₹60 per litre
₹25 per kg of TRS
₹1,600 per tonne
Ethanol density (for converting mass to litres)
0.789 kg/L
Daily margin per fermenter = (value of the ethanol produced − cost of the sugar charged − cost of the
distillation steam) ÷ cycle time, where the cycle time is the batch time plus the 8 h turnaround. A batch may be
ended only when the remaining sugar is at or below 5 g/L TRS. The plant pays for all the sugar charged,
including any left unfermented. Choose the initial sugar concentration within the range covered by the lab data
CHEMICAL PROCESS · 14
(160–260 g/L TRS), and the temperature between the lowest the plant can hold and 37 °C.
Distillation steam depends on wash strength. Use the plant’s design curve (wash strength in % v/v = ethanol in
g/L ÷ 7.89):
Wash strength (% v/v)
Steam per litre of ethanol (kg/L)
7
8
9
10
11
12
3.15
5. YOUR TASK
Level 1
2.94
2.77
2.64
2.53
2.44
13
2.36
14
2.29
• Build a kinetic model for biomass, sugar and ethanol (and anything else you can justify), and fit it to the
data. Justify each term from the data, not from a textbook.
• Decide which runs to fit, and give your reasons.
• Hold out at least one run, predict it, and compare.
Level 2
• Give an uncertainty for every parameter, and say which ones the data actually determine.
• Compare at least two model structures, and justify your choice.
• Close the carbon balance for every run.
Level 3
• Recommend an initial sugar concentration and fermentation temperature for October that maximise the
daily margin per fermenter. Show how your answer changes if the cooling water warms by 3 °C.
6. QUESTIONS TO ANSWER IN YOUR REPORT
1. Predict first: before fitting, look at the raw curves. Which runs show that something other than running out
of sugar stops the fermentation, and what do you think it is?
2. Which parameters can these data actually pin down? Show the evidence, and say what you will do about
the ones they cannot.
3. Is any run unfit for fitting your yeast model? Make your case with a carbon balance and the end-point
analysis, not with the fit residuals.
4. What is your overall ethanol yield, on what sugar basis, and why is it below the theoretical maximum?
Account for the gap.
5. Predict first: what does your model predict for a batch at 37 °C with 260 g/L sugar, and how far would
you trust that prediction?
6. Which single additional experiment would most reduce the uncertainty that matters for your
recommendation?
7. DELIVERABLES
• Code that reproduces every number and plot in your report from the raw files.
• Report: model equations, fitting method, parameter table with uncertainties, plots of fits and the held-out
prediction, carbon balances, answers to the six questions, and assumptions.
• Work log and AI-use note