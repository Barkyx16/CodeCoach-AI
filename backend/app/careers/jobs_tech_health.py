"""Technology and healthcare careers."""

from app.careers.profiles import job

TECHNOLOGY = "Technology"
HEALTHCARE = "Healthcare"

JOBS = [
    job(
        "software-engineer",
        "Software Engineer",
        TECHNOLOGY,
        "Design, build and maintain software, and prove it works with tests.",
        skills="debugging|code review|system design|writing tests|data structures and algorithms|API design|"
        "estimating work|technical communication",
        tools="Git|a debugger|CI pipelines|cloud platforms|issue trackers",
        situations="a production outage starts right after your deploy|a teammate's pull request has a subtle bug|"
        "a deadline moves up by a week|a requirement changes halfway through a feature|"
        "a test fails only on the build server|a customer reports data that looks corrupted|"
        "you inherit a large codebase with no documentation|a senior engineer rejects your design",
        people="product managers|other engineers|QA testers|on-call teammates",
        metrics="bug counts after release|deployment frequency|page load times|test coverage numbers",
        has_coding=True,
    ),
    job(
        "data-analyst",
        "Data Analyst",
        TECHNOLOGY,
        "Turn raw data into reports and answers that help a business decide.",
        skills="SQL querying|data cleaning|dashboard design|statistical reasoning|data storytelling|"
        "requirements gathering|spreadsheet modeling|A/B test analysis",
        tools="SQL databases|Excel|Tableau|Python notebooks|Power BI",
        situations="two dashboards show different numbers for the same metric|a stakeholder wants a report by tomorrow|"
        "you find a large chunk of missing data before a big meeting|an executive draws the wrong conclusion from your chart|"
        "a test result is statistically weak but the team wants to ship|the source data changes format without warning|"
        "three teams ask for urgent analysis on the same day|your analysis contradicts what leadership expects",
        people="business stakeholders|data engineers|executives|product managers",
        metrics="report turnaround times|data accuracy rates|dashboard usage|decisions supported by analysis",
    ),
    job(
        "data-scientist",
        "Data Scientist",
        TECHNOLOGY,
        "Build models and experiments that predict, explain and improve outcomes.",
        skills="feature engineering|model evaluation|experiment design|statistical modeling|data visualization|"
        "explaining models to non-experts|model monitoring|problem framing",
        tools="Python|Jupyter notebooks|scikit-learn|SQL|cloud ML platforms",
        situations="a model performs well offline but poorly in production|the training data turns out to be biased|"
        "leadership wants a prediction you think the data can't support|an experiment shows a surprising result|"
        "a model's accuracy slowly drifts down over months|a stakeholder asks why the model made one decision|"
        "you have one week to deliver a proof of concept|two features leak information about the target",
        people="product managers|data engineers|business leaders|software engineers",
        metrics="model accuracy|prediction error rates|experiment win rates|model latency",
    ),
    job(
        "product-manager",
        "Product Manager",
        TECHNOLOGY,
        "Decide what to build and why, and lead a team to ship it.",
        skills="prioritization|writing product requirements|customer discovery|roadmap planning|"
        "stakeholder alignment|defining success metrics|making trade-offs|launch planning",
        tools="roadmapping tools|analytics dashboards|user research platforms|issue trackers|prototyping tools",
        situations="engineering says your top feature will take three times longer than planned|"
        "two executives want opposite things on the roadmap|a launch gets poor customer feedback|"
        "a competitor ships the feature you were planning|usage data contradicts what customers say in interviews|"
        "a key engineer leaves mid-project|sales promises a customer a feature that isn't planned|"
        "a bug is found the day before launch",
        people="engineers|designers|executives|customers",
        metrics="feature adoption rates|customer retention|net promoter scores|time to ship",
    ),
    job(
        "ux-designer",
        "UX Designer",
        TECHNOLOGY,
        "Research users and design products that are easy and pleasant to use.",
        skills="user research|wireframing|usability testing|interaction design|accessibility|"
        "information architecture|presenting design decisions|design systems",
        tools="Figma|prototyping tools|survey tools|usability testing platforms|design system libraries",
        situations="usability tests show users can't find the main feature|an engineer says your design is too costly to build|"
        "a stakeholder wants a change that hurts usability|you have two days to design a new flow|"
        "research participants give conflicting feedback|the product fails an accessibility audit|"
        "marketing wants a flashy redesign right before launch|data shows users drop off at your new screen",
        people="product managers|engineers|users|marketing teams",
        metrics="task success rates|time on task|user satisfaction scores|drop-off rates",
    ),
    job(
        "it-support-specialist",
        "IT Support Specialist",
        TECHNOLOGY,
        "Keep people's computers, accounts and networks working, and fix them fast when they don't.",
        skills="troubleshooting|ticket prioritization|explaining technical issues simply|account management|"
        "hardware setup|network basics|security awareness|documentation",
        tools="ticketing systems|remote desktop tools|Active Directory|device management software|knowledge bases",
        situations="the whole office loses internet before a big meeting|an executive locks themselves out of their account|"
        "a user clicks a suspicious link in an email|twenty tickets arrive in the first hour of the day|"
        "a user is frustrated and blames you for a slow laptop|a printer fails on payroll day|"
        "you can't reproduce the problem a user describes|a new hire starts tomorrow and nothing is set up",
        people="employees|managers|vendors|the security team",
        metrics="ticket resolution times|first-contact resolution rates|user satisfaction scores|ticket backlogs",
        role="IT support specialist",
    ),
    job(
        "cybersecurity-analyst",
        "Cybersecurity Analyst",
        TECHNOLOGY,
        "Watch for attacks, investigate alerts and help the company stay secure.",
        skills="threat detection|incident response|log analysis|vulnerability management|risk assessment|"
        "security awareness training|access control|writing incident reports",
        tools="SIEM platforms|vulnerability scanners|firewalls|endpoint detection tools|threat intelligence feeds",
        situations="an alert suggests an attacker is inside the network|an employee reports a phishing email they clicked|"
        "a critical vulnerability is announced in software you run|a manager wants an exception to a security rule|"
        "hundreds of low-priority alerts flood in at once|a vendor asks for broad access to your systems|"
        "you find sensitive data stored where it shouldn't be|leadership asks if the company is safe after a public breach",
        people="IT teams|executives|employees|auditors",
        metrics="time to detect incidents|time to respond to incidents|patch completion rates|phishing click rates",
    ),
    job(
        "devops-engineer",
        "DevOps Engineer",
        TECHNOLOGY,
        "Automate how software is built, deployed and kept running.",
        skills="infrastructure as code|CI/CD pipelines|monitoring and alerting|incident management|cloud architecture|"
        "scripting|capacity planning|postmortem writing",
        tools="Docker|Kubernetes|Terraform|cloud consoles|monitoring dashboards",
        situations="a deployment breaks production at night|cloud costs double in one month|"
        "an alert fires every hour but nobody knows why|a team wants to skip the pipeline to ship faster|"
        "a database runs out of disk space|a certificate is about to expire on a customer-facing site|"
        "two teams need the same staging environment|a postmortem points to your automation",
        people="developers|engineering managers|security teams|on-call engineers",
        metrics="deployment frequency|change failure rates|time to restore service|cloud spending",
        role="DevOps engineer",
    ),
    job(
        "qa-tester",
        "QA Tester",
        TECHNOLOGY,
        "Find bugs before customers do, with careful manual and automated testing.",
        skills="test case design|bug reporting|exploratory testing|regression testing|test automation|"
        "risk-based testing|requirements review|cross-browser testing",
        tools="test management tools|bug trackers|Selenium|API testing tools|mobile device labs",
        situations="you find a serious bug the day before release|a developer says your bug can't be reproduced|"
        "requirements are vague and the feature is already built|you have only one day to test a large release|"
        "an automated test fails randomly|a bug you missed reaches customers|"
        "the team wants to cut testing time in half|two bugs block each other from being tested",
        people="developers|product managers|release managers|customer support teams",
        metrics="defects found before release|escaped defect rates|test coverage|test cycle times",
        role="QA tester",
    ),
    job(
        "business-analyst",
        "Business Analyst",
        TECHNOLOGY,
        "Translate business problems into clear requirements and better processes.",
        skills="requirements gathering|process mapping|stakeholder interviews|writing user stories|gap analysis|"
        "data analysis|change management|facilitating workshops",
        tools="process modeling tools|spreadsheets|issue trackers|documentation wikis|survey tools",
        situations="stakeholders disagree about what the system should do|a project is late because requirements keep changing|"
        "users refuse to adopt a new process|a key stakeholder misses every meeting|"
        "you discover a requirement nobody wrote down|the budget is cut halfway through a project|"
        "developers built something different from what the business wanted|a manager asks for a solution before the problem is clear",
        people="business stakeholders|developers|project managers|end users",
        metrics="requirements change rates|project delivery times|user adoption rates|process cycle times",
    ),
    job(
        "technical-writer",
        "Technical Writer",
        TECHNOLOGY,
        "Write the guides and documentation that help people use complex products.",
        skills="writing clear instructions|interviewing subject-matter experts|information architecture|editing|"
        "audience analysis|API documentation|style guide use|documentation maintenance",
        tools="documentation platforms|Markdown|screenshot and diagram tools|Git|content management systems",
        situations="engineers are too busy to review your drafts|a feature changes the week your guide ships|"
        "customers say the docs are confusing|you must document a product you have never used|"
        "two experts give you contradicting explanations|the docs site has hundreds of outdated pages|"
        "a manager wants documentation in half the usual time|support tickets reveal a missing guide",
        people="engineers|product managers|support teams|customers",
        metrics="support ticket volumes|documentation page views|search success rates|customer feedback ratings",
    ),
    job(
        "network-administrator",
        "Network Administrator",
        TECHNOLOGY,
        "Design, run and protect the networks a company depends on.",
        skills="network troubleshooting|firewall configuration|network design|monitoring|change management|"
        "VPN setup|capacity planning|documentation",
        tools="routers and switches|firewalls|network monitoring software|packet analyzers|configuration management tools",
        situations="the network goes down during business hours|a remote office reports very slow connections|"
        "a change you made causes an outage|an executive asks for an urgent firewall exception|"
        "monitoring shows unusual traffic at night|a key switch needs replacing with no maintenance window|"
        "the company opens a new office in two weeks|a vendor's equipment won't work with your network",
        people="employees|IT managers|vendors|security teams",
        metrics="network uptime|latency|incident counts|change success rates",
    ),
    # Healthcare
    job(
        "registered-nurse",
        "Registered Nurse",
        HEALTHCARE,
        "Assess patients, give medications and coordinate care on a clinical team.",
        skills="patient assessment|medication administration|care planning|patient education|infection control|"
        "clinical documentation|triage|shift handoffs",
        tools="electronic health records|IV pumps|vital-sign monitors|barcode medication scanners|nurse call systems",
        situations="a patient's vital signs drop suddenly during your shift|a family member is angry about a delay in care|"
        "you notice a medication order that looks wrong|two patients call for help at the same moment|"
        "a patient refuses a prescribed treatment|you are short-staffed for the whole shift|"
        "a new graduate nurse asks you for help mid-task|a doctor gives you a verbal order you are unsure about",
        people="patients|doctors|patients' families|charge nurses",
        metrics="patient satisfaction scores|medication error rates|patient fall rates|discharge times",
    ),
    job(
        "medical-assistant",
        "Medical Assistant",
        HEALTHCARE,
        "Room patients, take vitals and keep a clinic running smoothly.",
        skills="taking vital signs|patient intake|scheduling|medical records|phlebotomy|infection control|"
        "patient communication|insurance verification",
        tools="electronic health records|blood pressure monitors|scheduling software|EKG machines|phone systems",
        situations="the clinic is running an hour behind|a patient is nervous about a blood draw|"
        "a patient arrives without insurance information|you notice an abnormal reading in a patient's vitals|"
        "two providers need your help at the same time|a patient is upset about a billing error|"
        "a specimen label is missing information|a patient speaks a language you don't",
        people="patients|doctors|front-desk staff|nurses",
        metrics="patient wait times|appointment no-show rates|charting accuracy|patient satisfaction scores",
    ),
    job(
        "pharmacist",
        "Pharmacist",
        HEALTHCARE,
        "Check prescriptions for safety and help patients use their medicines well.",
        skills="prescription verification|drug interaction checks|patient counseling|immunizations|inventory management|"
        "insurance problem-solving|supervising technicians|medication therapy management",
        tools="pharmacy management systems|drug databases|automated dispensing machines|insurance portals|inventory systems",
        situations="a prescription has a dangerous drug interaction|a patient can't afford their medication|"
        "a doctor is unreachable and the patient needs their medicine today|the line is twenty people long|"
        "a technician makes a filling error|a patient asks for medicine they don't have a prescription for|"
        "a drug is on national shortage|a patient seems confused about how to take their pills",
        people="patients|doctors|pharmacy technicians|insurance companies",
        metrics="dispensing error rates|prescription wait times|vaccination counts|patient adherence rates",
    ),
    job(
        "pharmacy-technician",
        "Pharmacy Technician",
        HEALTHCARE,
        "Fill prescriptions accurately and keep the pharmacy organized.",
        skills="prescription filling|measuring and counting medication|customer service|insurance claims|"
        "inventory tracking|data entry|following safety procedures|compounding basics",
        tools="pharmacy software|counting trays|automated dispensing systems|insurance portals|cash registers",
        situations="a customer is angry that their prescription isn't ready|you notice a label doesn't match the drug|"
        "an insurance claim is rejected|the pharmacy is short on a common medicine|"
        "a customer asks you a clinical question|the drive-through and the counter are both busy|"
        "you suspect a forged prescription|a delivery arrives with damaged medicine",
        people="pharmacists|customers|insurance companies|delivery drivers",
        metrics="fill accuracy rates|prescription wait times|inventory accuracy|customer satisfaction scores",
    ),
    job(
        "physical-therapist",
        "Physical Therapist",
        HEALTHCARE,
        "Help people recover movement and manage pain through exercise and treatment.",
        skills="movement assessment|treatment planning|therapeutic exercise|patient motivation|progress tracking|"
        "manual therapy|home exercise programs|clinical documentation",
        tools="exercise equipment|electronic health records|ultrasound units|balance and gait tools|scheduling software",
        situations="a patient stops improving after several weeks|a patient skips their home exercises|"
        "a patient feels sharp pain during treatment|insurance only covers a few more visits|"
        "a patient's goals are unrealistic|your schedule is double-booked|"
        "a surgeon disagrees with your treatment plan|an older patient is afraid of falling",
        people="patients|doctors|insurance companies|patients' families",
        metrics="patient functional outcomes|visit completion rates|patient satisfaction scores|re-injury rates",
    ),
    job(
        "dental-hygienist",
        "Dental Hygienist",
        HEALTHCARE,
        "Clean teeth, spot problems early and teach patients to care for their mouths.",
        skills="teeth cleaning|periodontal assessment|taking X-rays|patient education|infection control|"
        "charting|managing anxious patients|time management",
        tools="ultrasonic scalers|dental X-ray machines|practice management software|intraoral cameras|sterilization equipment",
        situations="a patient is very anxious about the cleaning|you find signs of a serious problem the patient doesn't know about|"
        "your patient arrives twenty minutes late|a patient refuses X-rays|"
        "the dentist is running behind and patients are stacking up|a child won't sit still|"
        "a patient keeps skipping flossing despite advice|sterilization equipment fails mid-day",
        people="patients|dentists|front-office staff|dental assistants",
        metrics="patient retention|periodontal treatment acceptance|appointment timeliness|patient satisfaction scores",
    ),
    job(
        "physician-assistant",
        "Physician Assistant",
        HEALTHCARE,
        "Examine, diagnose and treat patients as part of a physician-led team.",
        skills="patient examination|differential diagnosis|ordering and reading tests|treatment planning|patient counseling|"
        "procedures|clinical documentation|collaborating with physicians",
        tools="electronic health records|diagnostic equipment|clinical decision support tools|lab systems|telehealth platforms",
        situations="a patient's symptoms don't fit any obvious diagnosis|a patient wants antibiotics they don't need|"
        "a test result comes back seriously abnormal late in the day|you disagree with your supervising physician|"
        "the waiting room is full and you're behind|a patient doesn't follow their treatment plan|"
        "you made a documentation error in a chart|a patient asks for a prescription that could be misused",
        people="patients|supervising physicians|nurses|specialists",
        metrics="diagnostic accuracy|patient wait times|readmission rates|patient satisfaction scores",
    ),
    job(
        "paramedic",
        "Paramedic",
        HEALTHCARE,
        "Give emergency medical care on scene and on the way to the hospital.",
        skills="scene safety assessment|emergency patient assessment|airway management|trauma care|"
        "calm communication under stress|radio reports|ambulance operations|patient care reports",
        tools="defibrillators|airway kits|ambulance equipment|radios|electronic patient care reporting",
        situations="you arrive at a scene that may not be safe|there are more injured people than you can treat at once|"
        "a patient refuses to go to the hospital|a bystander keeps interfering|"
        "your partner makes a treatment mistake|the closest hospital is on diversion|"
        "a patient's condition crashes during transport|a family member is panicking at the scene",
        people="patients|emergency room staff|police and fire crews|dispatchers",
        metrics="response times|patient outcomes|protocol compliance|report accuracy",
    ),
    job(
        "medical-receptionist",
        "Medical Receptionist",
        HEALTHCARE,
        "Greet patients, schedule visits and keep the front desk of a clinic calm and organized.",
        skills="patient check-in|appointment scheduling|insurance verification|phone etiquette|privacy protection|"
        "billing questions|calm communication|multitasking",
        tools="practice management software|phone systems|electronic health records|insurance portals|payment terminals",
        situations="a patient arrives for an appointment that isn't on the schedule|the phone keeps ringing while patients are waiting|"
        "a patient is angry about a long wait|someone asks for another patient's information|"
        "a provider calls in sick and the day is fully booked|a patient's insurance has expired|"
        "a patient seems to be having a medical emergency in the waiting room|the scheduling system goes down",
        people="patients|doctors|nurses|billing staff",
        metrics="check-in times|scheduling errors|no-show rates|patient satisfaction scores",
    ),
    job(
        "occupational-therapist",
        "Occupational Therapist",
        HEALTHCARE,
        "Help people do the everyday activities that matter to them after illness or injury.",
        skills="functional assessment|goal setting with patients|adaptive equipment recommendations|treatment planning|"
        "home safety evaluation|patient motivation|progress documentation|family training",
        tools="adaptive equipment|assessment tools|electronic health records|splinting materials|home modification checklists",
        situations="a patient is discouraged and wants to quit therapy|a family is doing too much for the patient|"
        "a home visit shows serious safety risks|a patient's goals conflict with their safety|"
        "insurance denies equipment the patient needs|a patient has trouble understanding instructions|"
        "your caseload doubles for a month|a patient makes a sudden big improvement",
        people="patients|patients' families|doctors|case managers",
        metrics="functional independence scores|goal achievement rates|discharge outcomes|patient satisfaction scores",
    ),
    job(
        "radiology-technologist",
        "Radiology Technologist",
        HEALTHCARE,
        "Take X-rays and scans that help doctors diagnose, while keeping patients safe.",
        skills="patient positioning|radiation safety|image quality checks|patient communication|equipment operation|"
        "infection control|following protocols|documentation",
        tools="X-ray machines|CT scanners|PACS image systems|lead shielding|scheduling software",
        situations="a patient can't stay still for the scan|an image is blurry and the patient has already left|"
        "a patient might be pregnant|the scanner breaks down with patients waiting|"
        "a doctor orders a scan that seems wrong for the symptoms|a trauma patient arrives during routine scans|"
        "a patient is claustrophobic|a coworker skips radiation safety steps",
        people="patients|radiologists|emergency staff|nurses",
        metrics="image repeat rates|patient wait times|radiation dose levels|equipment downtime",
    ),
    job(
        "home-health-aide",
        "Home Health Aide",
        HEALTHCARE,
        "Help people with daily care and safety in their own homes.",
        skills="personal care|safe patient transfers|observing changes in health|meal preparation|"
        "medication reminders|companionship|household safety|reporting to nurses",
        tools="care logs|mobility aids|blood pressure monitors|scheduling apps|emergency call devices",
        situations="your client falls while you are there|your client refuses to bathe|"
        "a family member criticizes how you do your job|you notice bruises you can't explain|"
        "your client seems more confused than usual|you're running late to your next client|"
        "your client asks you to do something outside your duties|the home is unsafe or very cluttered",
        people="clients|clients' families|nurses|care coordinators",
        metrics="visit punctuality|client satisfaction|incident reports|care plan completion",
    ),
]
