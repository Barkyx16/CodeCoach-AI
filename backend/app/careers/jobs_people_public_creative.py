"""People and administration, public service and legal, creative and media, and science and
engineering careers."""

from app.careers.profiles import job

ADMIN = "People & Administration"
PUBLIC = "Public Service & Legal"
CREATIVE = "Creative & Media"
SCIENCE = "Science & Engineering"

JOBS = [
    job(
        "hr-generalist",
        "HR Generalist",
        ADMIN,
        "Support employees and managers across hiring, policies, benefits and workplace issues.",
        skills="employee relations|policy interpretation|onboarding|benefits administration|workplace investigations|"
        "employment law basics|coaching managers|HR data management",
        tools="HR information systems|applicant tracking systems|benefits portals|case management tools|survey platforms",
        situations="an employee reports harassment by their manager|a manager wants to fire someone without documentation|"
        "two employees file complaints against each other|an employee asks for an accommodation|"
        "a manager shares confidential information about an employee|open enrollment closes with many employees confused|"
        "layoffs are announced and morale drops|an employee threatens legal action",
        people="employees|managers|executives|benefits providers",
        metrics="employee turnover|time to resolve cases|engagement scores|policy compliance",
        role="HR generalist",
    ),
    job(
        "recruiter",
        "Recruiter",
        ADMIN,
        "Find, attract and hire the right people for open roles.",
        skills="sourcing candidates|screening interviews|writing job descriptions|working with hiring managers|"
        "candidate experience|offer negotiation|pipeline management|diversity in hiring",
        tools="applicant tracking systems|LinkedIn Recruiter|job boards|scheduling tools|interview scorecards",
        situations="a hiring manager rejects every candidate you send|your top candidate accepts another offer|"
        "a role has been open for four months|a candidate asks for much more money than the budget|"
        "a hiring manager asks you to screen out candidates for a biased reason|you have twenty open roles at once|"
        "a candidate has a gap in their résumé they won't explain|feedback from interviewers is slow",
        people="candidates|hiring managers|interviewers|HR teams",
        metrics="time to fill|offer acceptance rates|quality of hire|candidate satisfaction",
    ),
    job(
        "administrative-assistant",
        "Administrative Assistant",
        ADMIN,
        "Keep an office or team organized with scheduling, communication and records.",
        skills="calendar management|organizing files|professional communication|prioritization|"
        "meeting coordination|data entry|confidentiality|problem-solving",
        tools="Microsoft Office|Google Workspace|calendar tools|phone systems|filing systems",
        situations="two managers give you urgent tasks at the same time|a meeting room is double-booked|"
        "you make a mistake in an important document|a visitor arrives unannounced and upset|"
        "you're asked to handle a task outside your role|the printer and copier fail before a big meeting|"
        "someone asks you for confidential information|your workload doubles while a coworker is out",
        people="managers|coworkers|clients and visitors|vendors",
        metrics="tasks completed on time|scheduling errors|response times|manager satisfaction",
    ),
    job(
        "executive-assistant",
        "Executive Assistant",
        ADMIN,
        "Manage an executive's time, communication and priorities so they can focus.",
        skills="executive calendar management|travel planning|anticipating needs|discretion|stakeholder communication|"
        "meeting preparation|project coordination|gatekeeping",
        tools="calendar tools|travel booking platforms|email|expense software|project management tools",
        situations="your executive's flight is canceled before a key meeting|two senior leaders both need the same time slot|"
        "your executive is in a bad mood and takes it out on you|you overhear confidential information|"
        "a board meeting packet has an error after it's sent|an important person insists on seeing your executive now|"
        "your executive forgets a commitment you reminded them about|you're asked to manage a project with no authority",
        people="executives|senior leaders|external partners|other assistants",
        metrics="calendar conflicts avoided|travel issues|meeting readiness|executive time saved",
    ),
    job(
        "office-manager",
        "Office Manager",
        ADMIN,
        "Run the office so people have what they need to do their work.",
        skills="facilities management|vendor management|budget tracking|onboarding support|"
        "policy enforcement|event coordination|supply management|problem-solving",
        tools="facilities request systems|accounting software|vendor contracts|inventory lists|office software",
        situations="the office air conditioning fails in a heat wave|the supply budget is cut|"
        "employees complain about a messy shared kitchen|a vendor overcharges you|"
        "the office is moving to a new building|a new hire arrives and nothing is ready|"
        "two teams fight over meeting space|there's a security incident in the building",
        people="employees|leadership|vendors|building management",
        metrics="office spending|request response times|employee satisfaction|vendor performance",
    ),
    job(
        "receptionist",
        "Receptionist",
        ADMIN,
        "Welcome visitors, answer calls and make a great first impression.",
        skills="greeting visitors|phone etiquette|message taking|scheduling|multitasking|"
        "security procedures|calm communication|basic administration",
        tools="phone systems|visitor management systems|calendar tools|email|office software",
        situations="a visitor is angry about waiting|the phone rings while three people stand at your desk|"
        "someone without an appointment insists on seeing a manager|you give a caller wrong information|"
        "a delivery arrives that nobody claims|a suspicious person tries to enter the building|"
        "you're asked to cover lunch for another department|a caller is rude and won't hang up",
        people="visitors|callers|employees|delivery drivers",
        metrics="call answer times|visitor wait times|message accuracy|visitor satisfaction",
    ),
    job(
        "data-entry-clerk",
        "Data Entry Clerk",
        ADMIN,
        "Enter and maintain accurate information in company systems.",
        skills="typing speed and accuracy|checking for errors|following data standards|confidentiality|"
        "organizing records|spotting inconsistencies|meeting quotas|reporting problems",
        tools="spreadsheets|databases|data entry software|scanners|keyboard shortcuts",
        situations="you discover you entered a batch of records incorrectly|source documents are unreadable|"
        "your quota increases but accuracy still matters|two documents contradict each other|"
        "the system crashes and you lose unsaved work|you're asked to enter data you think is wrong|"
        "a backlog builds up after a coworker leaves|the work feels repetitive and your focus slips",
        people="supervisors|coworkers|records teams|IT support",
        metrics="records entered per hour|error rates|backlog size|deadline completion",
    ),
    job(
        "project-manager",
        "Project Manager",
        ADMIN,
        "Plan and lead projects so they deliver what was promised, on time and on budget.",
        skills="project planning|risk management|stakeholder communication|scope management|"
        "team coordination|budget tracking|status reporting|running meetings",
        tools="project management software|Gantt charts|issue trackers|collaboration tools|spreadsheets",
        situations="the project is behind schedule and the deadline can't move|a stakeholder keeps adding requirements|"
        "two team members are in conflict|a key team member is pulled to another project|"
        "the budget is about to run out|a risk you flagged early actually happens|"
        "the sponsor loses interest in the project|status reports show green but you know it's red",
        people="sponsors|team members|stakeholders|vendors",
        metrics="on-time delivery|budget variance|scope changes|stakeholder satisfaction",
    ),
    # Public service & legal
    job(
        "police-officer",
        "Police Officer",
        PUBLIC,
        "Protect the public, respond to calls and enforce the law fairly.",
        skills="de-escalation|report writing|situational awareness|community relations|legal knowledge|"
        "decision-making under pressure|ethical judgment|physical readiness",
        tools="radios|body cameras|patrol cars|reporting software|first aid kits",
        situations="a domestic dispute call turns tense|a citizen is filming and yelling at you|"
        "you see a fellow officer use too much force|a person in a mental health crisis refuses help|"
        "a witness's story doesn't match the evidence|you're the first on scene at a serious accident|"
        "a community meeting turns hostile|a friend asks you to make a ticket go away",
        people="community members|fellow officers|supervisors|prosecutors",
        metrics="response times|case clearance rates|community complaints|report accuracy",
    ),
    job(
        "firefighter",
        "Firefighter",
        PUBLIC,
        "Respond to fires, rescues and medical emergencies as part of a crew.",
        skills="fire suppression|emergency medical care|teamwork under pressure|equipment checks|"
        "following the chain of command|physical fitness|hazard assessment|community safety education",
        tools="hoses and nozzles|breathing apparatus|ladders|rescue tools|radios",
        situations="you arrive at a fire and someone may still be inside|an order from your captain seems unsafe|"
        "a crew member is struggling after a traumatic call|equipment fails during a call|"
        "multiple calls come in at once|a resident refuses to leave a dangerous building|"
        "a new firefighter makes a dangerous mistake in training|you're exhausted after back-to-back calls",
        people="crew members|captains|the public|paramedics",
        metrics="response times|training hours|equipment readiness|injury rates",
    ),
    job(
        "paralegal",
        "Paralegal",
        PUBLIC,
        "Support lawyers with research, documents and case organization.",
        skills="legal research|drafting documents|case file management|discovery|deadline tracking|"
        "client communication|e-filing|attention to detail",
        tools="legal research databases|case management software|e-filing systems|document review platforms|Microsoft Office",
        situations="a filing deadline is tonight and the attorney is unreachable|you find an error in a filed document|"
        "a client calls asking for legal advice|two attorneys give you conflicting priorities|"
        "discovery documents arrive in a huge disorganized dump|a client is angry about the bill|"
        "you notice a possible conflict of interest|a court rejects an electronic filing",
        people="attorneys|clients|court clerks|opposing counsel's staff",
        metrics="deadlines met|document accuracy|billable hours|research turnaround",
    ),
    job(
        "lawyer",
        "Lawyer",
        PUBLIC,
        "Advise clients, argue their case and protect their legal interests.",
        skills="legal analysis|legal writing|negotiation|client counseling|oral advocacy|"
        "case strategy|ethics and professional responsibility|managing deadlines",
        tools="legal research databases|case management software|document review platforms|court e-filing|billing software",
        situations="a client wants you to make an argument you think is weak|you discover a mistake in a brief already filed|"
        "a client lies to you about a key fact|opposing counsel is hostile and unprofessional|"
        "two clients' interests start to conflict|a judge rules against you on a key motion|"
        "a client can't pay their bill mid-case|a settlement offer arrives the day before trial",
        people="clients|judges|opposing counsel|paralegals",
        metrics="case outcomes|billable hours|client retention|settlements reached",
    ),
    job(
        "social-worker",
        "Social Worker",
        PUBLIC,
        "Help people and families through hard times and connect them with support.",
        skills="needs assessment|case management|crisis intervention|advocacy|documentation|"
        "connecting clients to resources|setting boundaries|cultural humility",
        tools="case management software|resource directories|assessment tools|court reports|scheduling tools",
        situations="a child on your caseload may be in danger at home|a client refuses the help they need|"
        "your caseload is far above the recommended size|a client becomes angry and threatening|"
        "a family's situation affects you personally|a resource your client needs has a long waitlist|"
        "you disagree with your supervisor about a case|a client shares information you must report",
        people="clients|families|supervisors|community agencies",
        metrics="case outcomes|caseload size|documentation timeliness|client engagement",
    ),
    job(
        "legal-assistant",
        "Legal Assistant",
        PUBLIC,
        "Keep a law office organized with scheduling, documents and client contact.",
        skills="calendar and deadline management|document preparation|client intake|filing|"
        "billing records|confidentiality|professional communication|organizing case files",
        tools="case management software|calendaring systems|document templates|billing software|scanners",
        situations="a client calls upset and wants to speak to the attorney now|a court date is missing from the calendar|"
        "an attorney asks for a document you can't find|you accidentally email a document to the wrong person|"
        "two attorneys need urgent help at the same time|a new client's intake form is incomplete|"
        "a filing is rejected for a formatting error|a client asks what their chances are",
        people="attorneys|clients|court staff|paralegals",
        metrics="deadlines tracked|filing errors|client response times|billing accuracy",
    ),
    job(
        "correctional-officer",
        "Correctional Officer",
        PUBLIC,
        "Keep people safe and secure inside a correctional facility.",
        skills="maintaining security|de-escalation|observation|report writing|following procedures|"
        "fair treatment|emergency response|communication with inmates",
        tools="radios|surveillance systems|restraint equipment|logbooks|search equipment",
        situations="a fight breaks out in a common area|an inmate asks you for a favor|"
        "you find contraband during a search|a coworker treats inmates unfairly|"
        "an inmate threatens self-harm|a shift is badly understaffed|"
        "an inmate files a complaint against you|tension rises before a lockdown",
        people="inmates|fellow officers|supervisors|medical staff",
        metrics="incident counts|use-of-force reports|search completions|staff safety",
    ),
    job(
        "emergency-dispatcher",
        "Emergency Dispatcher",
        PUBLIC,
        "Answer 911 calls, gather information fast and send the right help.",
        skills="call triage|calm communication|gathering key information|multitasking|following protocols|"
        "radio communication|giving pre-arrival instructions|stress management",
        tools="computer-aided dispatch systems|radio consoles|mapping software|call recording systems|protocol cards",
        situations="a caller is panicking and can't give an address|several emergency calls come in at once|"
        "a caller hangs up mid-call|a child is calling about an emergency|"
        "units are delayed and the caller is getting worse|a caller is abusive|"
        "the dispatch system goes down|a call stays with you emotionally after your shift",
        people="callers|police officers|firefighters and paramedics|supervisors",
        metrics="call answer times|dispatch times|protocol compliance|call accuracy",
    ),
    # Creative & media
    job(
        "graphic-designer",
        "Graphic Designer",
        CREATIVE,
        "Create visuals that communicate ideas clearly and look great.",
        skills="layout and composition|typography|brand consistency|concept development|taking feedback|"
        "file preparation for print and web|presenting ideas|time management",
        tools="Adobe Photoshop|Adobe Illustrator|Figma|InDesign|stock asset libraries",
        situations="a client hates your first concept|the client asks for endless revisions|"
        "a deadline is moved up by three days|a printed piece comes back with the wrong colors|"
        "a stakeholder asks you to copy a competitor's design|feedback from two reviewers conflicts|"
        "the brief is vague|you discover a typo after a design goes live",
        people="clients|art directors|copywriters|marketing teams",
        metrics="revision rounds|projects delivered on time|client satisfaction|campaign results",
    ),
    job(
        "video-editor",
        "Video Editor",
        CREATIVE,
        "Shape raw footage into a story that keeps people watching.",
        skills="story structure|pacing|color correction|audio mixing|motion graphics|"
        "organizing footage|taking direction|meeting deadlines",
        tools="Adobe Premiere Pro|DaVinci Resolve|After Effects|audio software|storage drives",
        situations="a client wants major changes the day before release|footage is missing a key shot|"
        "your project file gets corrupted|the director and the client want different cuts|"
        "you're asked to cut a 10-minute video to 60 seconds|music rights fall through at the last minute|"
        "audio quality is poor in the main interview|analytics show viewers drop off early",
        people="directors|producers|clients|motion designers",
        metrics="audience retention|turnaround times|revision rounds|views and engagement",
    ),
    job(
        "photographer",
        "Photographer",
        CREATIVE,
        "Capture images that tell a story and meet a client's needs.",
        skills="composition|lighting|directing subjects|photo editing|client communication|"
        "equipment care|pricing and contracts|shot planning",
        tools="cameras and lenses|lighting kits|Adobe Lightroom|Photoshop|online galleries",
        situations="it rains on an outdoor shoot|a client is unhappy with the photos|"
        "a memory card fails after a wedding|a subject is uncomfortable in front of the camera|"
        "a client wants extra work without paying|someone uses your photos without permission|"
        "you're shooting in a location with terrible light|a client wants edits that look unnatural",
        people="clients|models and subjects|editors|venue staff",
        metrics="client bookings|referrals|delivery times|client satisfaction",
    ),
    job(
        "journalist",
        "Journalist",
        CREATIVE,
        "Find, verify and report stories that inform the public.",
        skills="news judgment|interviewing|fact-checking|writing on deadline|source development|"
        "media ethics|research|multimedia storytelling",
        tools="content management systems|recording apps|public records databases|social media|editing software",
        situations="a source asks to go off the record halfway through an interview|you're on deadline and can't confirm a key fact|"
        "a powerful person pressures you to drop a story|you publish an error|"
        "a story you're covering affects someone you know|a viral claim spreads and readers want answers now|"
        "an editor cuts your story heavily|a source stops returning your calls",
        people="sources|editors|readers|public officials",
        metrics="stories published|accuracy and corrections|reader engagement|scoops",
    ),
    job(
        "copywriter",
        "Copywriter",
        CREATIVE,
        "Write words that persuade people to act, from ads to websites.",
        skills="headline writing|brand voice|persuasive writing|concept development|editing|"
        "audience research|working with designers|taking feedback",
        tools="Google Docs|content management systems|A/B testing tools|brief templates|style guides",
        situations="a client rejects every headline you write|legal wants to remove the best line|"
        "you have to write for a product you find boring|two stakeholders want different messages|"
        "your copy underperforms in an A/B test|a deadline is cut in half|"
        "you're asked to write a claim you think is misleading|the brief changes after you've finished",
        people="clients|creative directors|designers|legal reviewers",
        metrics="conversion rates|click-through rates|approval rounds|deadlines met",
    ),
    job(
        "architect",
        "Architect",
        CREATIVE,
        "Design buildings that are safe, useful and beautiful, and guide them to completion.",
        skills="design concepts|building codes|construction documents|client presentations|"
        "coordinating engineers|budget-aware design|site visits|sustainable design",
        tools="Revit|AutoCAD|SketchUp|rendering software|building codes",
        situations="the client's budget can't cover their wish list|the contractor finds an error in your drawings|"
        "a code review rejects part of your design|the client changes the program late in design|"
        "an engineer says your design isn't structurally feasible|the project is delayed by permit issues|"
        "a neighbor group opposes the project|your design fails an energy requirement",
        people="clients|contractors|engineers|planning officials",
        metrics="project budgets|schedule adherence|change orders|client satisfaction",
    ),
    # Science & engineering
    job(
        "mechanical-engineer",
        "Mechanical Engineer",
        SCIENCE,
        "Design and test machines and products that work reliably.",
        skills="CAD design|engineering analysis|prototyping|testing and validation|design for manufacturing|"
        "root cause analysis|technical documentation|cross-team collaboration",
        tools="SolidWorks|finite element analysis software|3D printers|test rigs|spreadsheets",
        situations="a prototype fails a key test|manufacturing says your design is too costly to make|"
        "a supplier part doesn't meet spec|a customer reports a product failure in the field|"
        "the schedule leaves no time for full testing|you disagree with a senior engineer's design|"
        "a requirement changes after tooling is ordered|a test result is hard to explain",
        people="manufacturing teams|project managers|suppliers|test technicians",
        metrics="design cycle times|test pass rates|product cost|field failure rates",
    ),
    job(
        "civil-engineer",
        "Civil Engineer",
        SCIENCE,
        "Design and oversee roads, bridges, water systems and other infrastructure.",
        skills="structural analysis|site design|code compliance|construction oversight|project management|"
        "permitting|technical writing|working with the public",
        tools="AutoCAD Civil 3D|structural analysis software|GIS|survey data|project scheduling tools",
        situations="field conditions don't match the design|a contractor wants to substitute a cheaper material|"
        "a public meeting opposes your project|a permit is delayed for months|"
        "you find an error in calculations already approved|the budget is cut mid-design|"
        "a storm damages a site under construction|an inspector questions your design",
        people="contractors|government agencies|the public|other engineers",
        metrics="project schedules|construction costs|safety records|design review comments",
    ),
    job(
        "electrical-engineer",
        "Electrical Engineer",
        SCIENCE,
        "Design and test electrical systems, circuits and devices.",
        skills="circuit design|power systems analysis|testing and debugging hardware|reading schematics|"
        "safety standards|simulation|documentation|working with manufacturing",
        tools="circuit simulation software|oscilloscopes|PCB design tools|multimeters|MATLAB",
        situations="a board fails testing intermittently|a component goes out of stock|"
        "a design doesn't pass certification|manufacturing reports a high failure rate|"
        "the deadline won't allow another design revision|a customer reports overheating|"
        "a colleague's design has a safety flaw|requirements change after prototypes are built",
        people="manufacturing teams|firmware engineers|suppliers|certification labs",
        metrics="first-pass yield|design revisions|product cost|certification pass rates",
    ),
    job(
        "lab-technician",
        "Lab Technician",
        SCIENCE,
        "Run tests and experiments accurately and keep the lab safe and organized.",
        skills="sample preparation|following protocols|lab safety|equipment calibration|record keeping|"
        "quality control|data entry|troubleshooting instruments",
        tools="microscopes|centrifuges|pipettes|lab information management systems|analytical instruments",
        situations="a test result looks wrong|an instrument fails in the middle of a run|"
        "a sample is mislabeled|a coworker skips a safety step|"
        "a rush request arrives with a full queue|you contaminate a sample|"
        "a supervisor asks you to report a result you're unsure of|chemical supplies run out",
        people="scientists|lab managers|quality teams|clients",
        metrics="turnaround times|error rates|quality control pass rates|safety incidents",
    ),
    job(
        "environmental-scientist",
        "Environmental Scientist",
        SCIENCE,
        "Study environmental problems and recommend ways to protect people and nature.",
        skills="field sampling|data analysis|environmental regulations|report writing|site assessment|"
        "risk communication|GIS mapping|project management",
        tools="sampling equipment|GIS software|statistical software|lab services|field data apps",
        situations="sampling shows contamination above legal limits|a client wants findings softened|"
        "weather ruins a field sampling day|data from two labs disagree|"
        "community members are worried and want answers now|a regulation changes mid-project|"
        "a site is unsafe to access|a report deadline arrives before lab results",
        people="clients|regulators|community members|lab partners",
        metrics="report quality|compliance outcomes|project deadlines|data accuracy",
    ),
    job(
        "chemist",
        "Chemist",
        SCIENCE,
        "Develop and analyze substances through careful experiments.",
        skills="experiment design|analytical techniques|lab safety|data interpretation|method development|"
        "documentation|troubleshooting reactions|scientific communication",
        tools="chromatography systems|spectrometers|fume hoods|electronic lab notebooks|data analysis software",
        situations="an experiment can't be reproduced|results contradict your hypothesis|"
        "a safety incident happens in the lab|a project deadline doesn't allow more experiments|"
        "an instrument gives drifting results|a colleague questions your data|"
        "a promising compound turns out unstable|you're asked to scale up a reaction quickly",
        people="research scientists|lab managers|quality teams|product teams",
        metrics="experiment success rates|method accuracy|project milestones|safety incidents",
    ),
]
