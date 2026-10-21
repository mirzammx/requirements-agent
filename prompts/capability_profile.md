# Rug-Rel SBU-2 (Power Electronics) — Capability Profile

> DRAFT. Built from the SBU-2 BD presentation and a past technical compliance
> submission. Items marked **[CONFIRM]** need Mahadevan's input before the profile
> is treated as authoritative.

## What we do

Design, development, qualification and supply of power electronics for:

- Defence: ground, naval and air force platforms (DRDO labs, defence PSUs, private defence)
- Airborne / avionics
- Railways
- Drones and EV (battery chargers, low to medium wattage)

## Product lines

**Custom power supplies**: any shape, enclosure or form factor
- DC input: 28, 48, 72, 110, 270 VDC
- AC input: single- or three-phase; 115, 230, 440 VAC; universal 90–264 / 180–264 VAC; 400 Hz airborne
- Outputs: multiple rails (e.g. 28 V, ±12 V, 5 V, 3.3 V), tens of watts up to several kW, redundant or isolated outputs
- Cooling: conduction (sealed / avionics), forced air, natural convection, liquid (cold plate)
- Connectors: MIL-grade circular, rectangular, MIL-DTL-24308 D-sub, PCB-mounted

**Standard-architecture power supplies**
- VPX / VITA-62: 3U and 6U, 4HP / 10HP, conduction or forced-air cooled, AC and DC input
- cPCI: 3U and 6U, 10HP, convection or forced-air, AC and DC input
- VME: 3U and 6U, conduction or forced-air, AC and DC input

**Related products**
- Rugged UPS for defence
- Chargers / adapters for rugged laptops and LRUs
- Power interface boards for VPX / cPCI / VME supplies
- Test jigs for VPX / cPCI / VME supplies
- EMI/EMC filters

## Evidence of past work

- **Airborne ATRU (three-phase AC to DC), defence avionics customer, compliance submitted Sep 2026.**
  115 VAC 3-phase 400 Hz in; five rails (24 V/40 A, −5 V, 2× 5.2 V, 10 V), roughly 1.1 kW;
  power sequencing, per-rail fault indication, I²C temperature telemetry; liquid cold plate;
  MIL-STD-461G, MIL-STD-704D/F, MIL-STD-810H / JSS 55555; ESS per DGAQA directive;
  CEMILAC/DGAQA document set. **[CONFIRM: won / delivered / still under evaluation?]**
- Photos of delivered custom enclosures and VPX / cPCI modules appear in the BD deck. **[CONFIRM: list of named past projects and customers]**

## Standards and processes we work to

- EMI/EMC: MIL-STD-461 (C, E, G)
- Aircraft power: MIL-STD-704 (D, E, F)
- Environmental: MIL-STD-810 (G, H), JSS 55555
- Airworthiness / quality: CEMILAC, DGAQA, RCMA clearances; NABL-accredited test labs; ESS
- Documentation: SOP, BOM, MPD, MDI, FTP, ATP, QAP, MTBF / derating reports

## Commercial terms we have accepted before

From the ATRU submission. These are not deal-breakers by themselves:
- Transfer of IPR and design data (Gerbers, schematics) to the customer
- 15-year obsolescence-free components; 20-year product support
- 2-year warranty with replacement and a 1-month turnaround
- 5% performance bank guarantee
- Changes based on integration and flight-trial feedback at no extra cost

## Open items for Mahadevan

- **[CONFIRM]** AS9100 / ISO 9001 certification status
- **[CONFIRM]** MSE / Udyam registration and category
- **[CONFIRM]** CEMILAC approvals actually obtained (versus processes followed)
- **[CONFIRM]** Minimum order value or project size worth bidding on
- **[CONFIRM]** Hard no's: product types, customers, or terms we always decline
- **[CONFIRM]** Current team capacity: how many parallel developments are realistic
- **[CONFIRM]** Upper limits: maximum power and power density demonstrated, longest hold-up achieved

## Questions BD should get answered (SBU-2 MIR checklist)

Use these to word the open questions on each bid card.

Technical: input voltage; number of outputs and current per rail; total output power;
cooling method; form factor and dimensions; end application; operating and storage
temperature; project status (new development, in production, or an additional source
for an existing design); budget limits.

Non-technical: initial quantity, prototype duration and production forecast;
competitor information; the customer's pain point and where we are strongest.
