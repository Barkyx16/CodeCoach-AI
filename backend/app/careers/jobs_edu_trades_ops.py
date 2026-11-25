"""Education, skilled trades and construction, and operations and logistics careers."""

from app.careers.profiles import job

EDUCATION = "Education"
TRADES = "Skilled Trades & Construction"
OPERATIONS = "Operations & Logistics"

JOBS = [
    job(
        "elementary-teacher",
        "Elementary School Teacher",
        EDUCATION,
        "Teach young children core subjects and help each one grow.",
        skills="lesson planning|classroom management|differentiated instruction|assessment|parent communication|"
        "social-emotional learning|reading instruction|building routines",
        tools="learning management systems|smartboards|curriculum materials|gradebooks|educational apps",
        situations="a student is disrupting the class every day|a parent emails angry about a grade|"
        "several students are far behind in reading|a lesson completely falls flat|"
        "a student tells you something worrying about home|you have a substitute plan due in an hour|"
        "two students get into a fight at recess|the principal observes you on a chaotic day",
        people="students|parents|principals|other teachers",
        metrics="reading levels|test scores|attendance rates|behavior incidents",
        role="elementary school teacher",
    ),
    job(
        "high-school-teacher",
        "High School Teacher",
        EDUCATION,
        "Teach a subject to teenagers and prepare them for life after school.",
        skills="lesson planning|classroom management|engaging teenagers|grading and feedback|"
        "subject expertise|differentiated instruction|parent communication|mentoring students",
        tools="learning management systems|online assessment tools|presentation software|gradebooks|lab or subject equipment",
        situations="half the class fails a test|a student is caught cheating|"
        "a student is always on their phone|a parent wants a grade changed|"
        "a student seems depressed|you're asked to teach a subject outside your specialty|"
        "a class discussion turns heated|a student says your class is pointless",
        people="students|parents|department heads|counselors",
        metrics="pass rates|assignment completion|attendance|student engagement",
    ),
    job(
        "teaching-assistant",
        "Teaching Assistant",
        EDUCATION,
        "Support teachers and give students extra help in the classroom.",
        skills="small-group instruction|supporting students with special needs|behavior support|"
        "preparing materials|following the teacher's plan|patience|observation and note-taking|communication with teachers",
        tools="classroom materials|learning apps|behavior charts|photocopiers|student records",
        situations="a student refuses to work with you|you disagree with how the teacher handles a student|"
        "a student melts down in the middle of a lesson|the teacher is absent and you're left in charge|"
        "a student asks you for help on a topic you don't understand|two students need you at the same time|"
        "a parent asks you about their child's progress|you notice a student being bullied",
        people="students|teachers|parents|special education staff",
        metrics="student progress|behavior incidents|small-group outcomes|teacher feedback",
    ),
    job(
        "school-counselor",
        "School Counselor",
        EDUCATION,
        "Support students' wellbeing, academics and plans for the future.",
        skills="one-on-one counseling|crisis response|college and career advising|group facilitation|"
        "working with families|confidentiality|referrals to outside help|data-driven planning",
        tools="student information systems|career planning software|counseling records|scheduling tools|referral directories",
        situations="a student tells you they are thinking about self-harm|a parent demands to know what their child told you|"
        "a senior has no plan after graduation|a teacher says a student is lazy|"
        "a student is being bullied online|you have 400 students and limited time|"
        "a student wants a schedule change that hurts their goals|a family is facing homelessness",
        people="students|parents|teachers|administrators",
        metrics="graduation rates|college application rates|counseling sessions held|attendance improvements",
    ),
    job(
        "tutor",
        "Tutor",
        EDUCATION,
        "Help individual students understand material and build confidence.",
        skills="diagnosing knowledge gaps|explaining concepts simply|building confidence|lesson planning|"
        "progress tracking|test preparation|adapting to learning styles|parent communication",
        tools="video call platforms|practice materials|online whiteboards|scheduling apps|assessment tools",
        situations="a student isn't improving after several sessions|a parent expects a grade jump in two weeks|"
        "a student keeps canceling sessions|a student wants you to do their homework|"
        "you don't know how to solve a problem the student brings|a student shuts down when they get something wrong|"
        "a student has an undiagnosed learning difficulty|a student is bored and distracted",
        people="students|parents|teachers|tutoring coordinators",
        metrics="grade improvements|test score gains|session attendance|student confidence",
    ),
    job(
        "special-education-teacher",
        "Special Education Teacher",
        EDUCATION,
        "Teach students with disabilities and make sure they get the support they need.",
        skills="individualized education plans|adapted instruction|behavior support plans|progress monitoring|"
        "collaboration with families|working with aides|assistive technology|legal compliance",
        tools="IEP software|assistive technology devices|visual schedules|data collection sheets|sensory tools",
        situations="a student has a serious behavior episode|a parent disagrees with the IEP|"
        "a general education teacher won't follow accommodations|your caseload paperwork is overdue|"
        "a student makes no progress on a goal|an aide isn't following the behavior plan|"
        "a student is excluded by peers|a new student arrives with no records",
        people="students|parents|general education teachers|aides",
        metrics="IEP goal progress|behavior incidents|compliance deadlines met|inclusion time",
    ),
    job(
        "preschool-teacher",
        "Preschool Teacher",
        EDUCATION,
        "Help young children learn through play and build early skills.",
        skills="play-based learning|early literacy|classroom routines|child development knowledge|"
        "parent communication|health and safety|observing and documenting development|positive guidance",
        tools="learning centers|observation records|parent communication apps|art and play materials|curriculum guides",
        situations="a child bites another child|a parent is upset their child came home dirty|"
        "a child cries every morning at drop-off|a child shows signs of a developmental delay|"
        "a child has an allergic reaction|a co-teacher handles discipline very differently from you|"
        "the class is overwhelmed and chaotic after lunch|a parent picks up late again",
        people="children|parents|co-teachers|center directors",
        metrics="developmental milestones|incident reports|parent satisfaction|attendance",
    ),
    job(
        "academic-advisor",
        "Academic Advisor",
        EDUCATION,
        "Guide college students through their courses, degree and goals.",
        skills="degree planning|advising conversations|knowing academic policies|referrals to campus support|"
        "early intervention|record keeping|motivational interviewing|cultural sensitivity",
        tools="student information systems|degree audit tools|appointment scheduling software|early alert systems|email",
        situations="a student is about to lose financial aid because of grades|a student wants a course the rules don't allow|"
        "a student is overwhelmed and talking about dropping out|you gave a student wrong advice about a requirement|"
        "registration week brings back-to-back appointments|a parent calls demanding information about their adult child|"
        "a student keeps missing appointments|a student is undecided about their major in their third year",
        people="students|faculty|financial aid staff|parents",
        metrics="retention rates|graduation rates|advising appointments|students on academic probation",
    ),
    # Skilled trades & construction
    job(
        "electrician",
        "Electrician",
        TRADES,
        "Install, repair and maintain electrical systems safely and to code.",
        skills="reading blueprints|electrical troubleshooting|code compliance|wiring installation|lockout/tagout safety|"
        "estimating materials|customer communication|panel upgrades",
        tools="multimeters|wire strippers and crimpers|conduit benders|circuit testers|electrical code books",
        situations="you find dangerous wiring left by a previous contractor|a customer wants work that won't pass code|"
        "the job runs over the estimate|an inspection fails|"
        "a circuit keeps tripping and you can't find why|you're asked to work on a live circuit to save time|"
        "an apprentice makes a mistake on site|the materials you need are back-ordered",
        people="customers|general contractors|inspectors|apprentices",
        metrics="inspection pass rates|jobs completed on time|callbacks|safety incidents",
    ),
    job(
        "plumber",
        "Plumber",
        TRADES,
        "Install and repair pipes, fixtures and water systems.",
        skills="leak diagnosis|pipe installation|reading plans|drain cleaning|water heater service|"
        "code compliance|customer communication|estimating jobs",
        tools="pipe wrenches|drain snakes|inspection cameras|soldering torches|pressure testers",
        situations="a burst pipe is flooding a home at night|a customer disputes your bill|"
        "the problem turns out much bigger than the estimate|you damage a customer's floor during a repair|"
        "an inspector fails your work|a customer wants a cheap fix that won't last|"
        "you have three emergency calls at once|the parts you need aren't available",
        people="homeowners|general contractors|inspectors|suppliers",
        metrics="first-time fix rates|callbacks|customer reviews|jobs completed per day",
    ),
    job(
        "carpenter",
        "Carpenter",
        TRADES,
        "Build and repair structures and finishes from wood and other materials.",
        skills="measuring and layout|framing|finish carpentry|reading blueprints|tool safety|"
        "estimating materials|problem-solving on site|working with other trades",
        tools="circular saws|nail guns|levels|tape measures|framing squares",
        situations="the plans don't match what's on site|a customer changes the design mid-job|"
        "you cut a costly board wrong|other trades are behind and holding you up|"
        "the weather stops work for days|a coworker ignores safety rules|"
        "materials arrive damaged|you're asked to finish a job faster than is safe",
        people="customers|general contractors|other trades|apprentices",
        metrics="jobs on schedule|material waste|rework rates|safety incidents",
    ),
    job(
        "hvac-technician",
        "HVAC Technician",
        TRADES,
        "Install and repair heating, cooling and ventilation systems.",
        skills="system diagnostics|refrigerant handling|electrical troubleshooting|installation|preventive maintenance|"
        "customer communication|safety procedures|explaining repair options",
        tools="refrigerant gauges|multimeters|leak detectors|thermostats|service software",
        situations="a family's heat is out during a freeze|a customer is angry about the cost of a repair|"
        "you can't find the cause of an intermittent problem|a system needs replacing but the customer can't afford it|"
        "you have more calls than hours in a heat wave|a part is wrong when you arrive|"
        "a customer asks you to skip a safety check|your manager pushes you to upsell unnecessary repairs",
        people="homeowners|dispatchers|building managers|parts suppliers",
        metrics="first-time fix rates|calls completed|customer reviews|maintenance agreements sold",
        role="HVAC technician",
    ),
    job(
        "welder",
        "Welder",
        TRADES,
        "Join metal parts with strong, clean welds that meet specifications.",
        skills="weld quality|reading welding symbols|metal preparation|welding safety|fit-up|"
        "inspecting welds|working to specifications|equipment maintenance",
        tools="MIG welders|TIG welders|grinders|welding helmets|measuring tools",
        situations="a weld fails inspection|you're asked to weld a material you've rarely worked with|"
        "a deadline forces you to rush|the drawings are unclear|"
        "your equipment malfunctions mid-job|a coworker removes their safety gear|"
        "a part is warped after welding|you notice a defect in someone else's weld",
        people="supervisors|inspectors|fabricators|engineers",
        metrics="weld rejection rates|productivity|safety incidents|rework hours",
    ),
    job(
        "construction-project-manager",
        "Construction Project Manager",
        TRADES,
        "Run building projects so they finish safely, on time and on budget.",
        skills="scheduling|budget control|subcontractor management|safety management|client communication|"
        "reading plans|change order management|risk management",
        tools="project scheduling software|estimating tools|construction management platforms|blueprints|daily reports",
        situations="the project is three weeks behind schedule|a subcontractor walks off the job|"
        "the client wants major changes without more budget|a worker is injured on site|"
        "material prices jump 20%|an inspector shuts down work|"
        "two trades blame each other for a delay|the design has an error discovered during construction",
        people="clients|subcontractors|architects|site workers",
        metrics="schedule performance|budget variance|safety incident rates|change order totals",
    ),
    job(
        "auto-mechanic",
        "Auto Mechanic",
        TRADES,
        "Diagnose and repair vehicles so they run safely and reliably.",
        skills="vehicle diagnostics|brake and suspension repair|engine repair|using scan tools|"
        "explaining repairs to customers|estimating jobs|preventive maintenance|shop safety",
        tools="diagnostic scanners|lifts|torque wrenches|repair manuals|shop management software",
        situations="a customer's car comes back with the same problem|a customer doesn't trust your diagnosis|"
        "you find a safety issue the customer didn't ask about|the repair takes far longer than quoted|"
        "your manager wants you to upsell unneeded repairs|a part you installed fails|"
        "an electric vehicle comes in and you have little training on it|three cars need to be done by closing",
        people="customers|service advisors|shop managers|parts suppliers",
        metrics="comebacks|billed hours|customer satisfaction|repair accuracy",
    ),
    job(
        "maintenance-technician",
        "Maintenance Technician",
        TRADES,
        "Keep buildings and equipment running through repairs and preventive care.",
        skills="troubleshooting|preventive maintenance|electrical basics|plumbing basics|HVAC basics|"
        "work order management|safety procedures|prioritizing repairs",
        tools="hand and power tools|multimeters|work order systems|lockout/tagout kits|maintenance logs",
        situations="a production line stops and everyone is waiting on you|you get five urgent work orders at once|"
        "a repair needs a part that will take a week|a tenant complains repeatedly about the same issue|"
        "preventive maintenance keeps getting skipped for urgent work|a contractor does poor-quality work|"
        "you're asked to fix something outside your training|a safety hazard is ignored by management",
        people="facility managers|production supervisors|tenants|contractors",
        metrics="equipment downtime|work orders completed|preventive maintenance completion|repeat repairs",
    ),
    job(
        "construction-laborer",
        "Construction Laborer",
        TRADES,
        "Do the physical work that keeps construction sites moving.",
        skills="site safety|material handling|operating basic equipment|following instructions|teamwork|"
        "site cleanup|reading basic plans|working in all weather",
        tools="hand tools|power tools|wheelbarrows|safety harnesses|concrete mixers",
        situations="a supervisor asks you to do something unsafe|you see a coworker get hurt|"
        "the crew is behind schedule|you don't understand an instruction|"
        "the weather turns dangerous|a coworker is not doing their share|"
        "equipment you need is broken|you're assigned to a task you've never done",
        people="foremen|coworkers|equipment operators|site supervisors",
        metrics="safety incidents|tasks completed on time|attendance|productivity",
    ),
    job(
        "heavy-equipment-operator",
        "Heavy Equipment Operator",
        TRADES,
        "Operate bulldozers, excavators and cranes safely and precisely.",
        skills="equipment operation|pre-shift inspections|site safety|reading grade plans|"
        "communication with spotters|preventive maintenance|precision work|load awareness",
        tools="excavators|bulldozers|loaders|GPS grading systems|radios",
        situations="your machine has a warning light during a critical job|a spotter gives an unclear signal|"
        "ground conditions look unstable|you're asked to operate equipment you're not certified on|"
        "a worker walks into your swing radius|the schedule pushes you to skip an inspection|"
        "you hit an unmarked utility line|bad weather makes the site slippery",
        people="site supervisors|spotters|mechanics|other operators",
        metrics="safety incidents|equipment uptime|grading accuracy|fuel use",
    ),
    # Operations & logistics
    job(
        "warehouse-associate",
        "Warehouse Associate",
        OPERATIONS,
        "Pick, pack and ship orders accurately and safely.",
        skills="order picking|packing|inventory accuracy|forklift safety|meeting productivity targets|"
        "teamwork|following procedures|reporting problems",
        tools="handheld scanners|forklifts|pallet jacks|warehouse management systems|label printers",
        situations="you're behind your pick rate and the shift is almost over|you find an item in the wrong location|"
        "a coworker drives a forklift unsafely|a shipment is damaged|"
        "your scanner stops working|you're asked to work overtime again|"
        "an order is missing items at packing|you spot a safety hazard in an aisle",
        people="supervisors|coworkers|drivers|inventory teams",
        metrics="pick rates|order accuracy|safety incidents|on-time shipments",
    ),
    job(
        "supply-chain-analyst",
        "Supply Chain Analyst",
        OPERATIONS,
        "Use data to keep products flowing from suppliers to customers efficiently.",
        skills="demand forecasting|inventory analysis|supplier performance analysis|data reporting|"
        "process improvement|cost analysis|scenario planning|cross-team communication",
        tools="ERP systems|Excel|SQL|planning software|business intelligence tools",
        situations="a key supplier announces a two-month delay|inventory is too high and cash is tight|"
        "a forecast misses badly and stores run out|a new tariff raises costs overnight|"
        "the data in two systems doesn't match|leadership wants a cheaper supplier with lower quality|"
        "a port strike delays shipments|sales runs a promotion without telling supply chain",
        people="suppliers|planners|sales teams|warehouse managers",
        metrics="forecast accuracy|inventory turns|fill rates|logistics costs",
    ),
    job(
        "logistics-coordinator",
        "Logistics Coordinator",
        OPERATIONS,
        "Schedule and track shipments so they arrive on time and on budget.",
        skills="shipment scheduling|carrier management|tracking and tracing|documentation|problem-solving|"
        "cost control|customer updates|customs basics",
        tools="transportation management systems|carrier portals|tracking software|Excel|shipping documents",
        situations="a truck breaks down with a time-critical load|a customer says their order never arrived|"
        "a carrier raises rates without notice|shipping paperwork has an error at customs|"
        "a holiday rush doubles volume|two urgent shipments need the last available truck|"
        "a shipment arrives damaged|weather closes a major route",
        people="carriers|customers|warehouse staff|sales teams",
        metrics="on-time delivery rates|freight costs|damage claims|shipment visibility",
    ),
    job(
        "truck-driver",
        "Truck Driver",
        OPERATIONS,
        "Deliver freight safely and on time over long or regional routes.",
        skills="safe driving|trip planning|vehicle inspections|hours-of-service compliance|cargo securement|"
        "customer interaction at delivery|time management|handling emergencies",
        tools="electronic logging devices|GPS|trucks and trailers|inspection checklists|dispatch apps",
        situations="you're running out of legal driving hours before the delivery|a receiver refuses your load|"
        "your truck breaks down on the highway|dispatch pushes you to drive in a dangerous storm|"
        "your load shifts during transit|you're stuck in traffic and will be late|"
        "an inspection finds a problem with your truck|you feel too tired to drive safely",
        people="dispatchers|shippers and receivers|mechanics|other drivers",
        metrics="on-time deliveries|safety record|fuel efficiency|inspection results",
    ),
    job(
        "delivery-driver",
        "Delivery Driver",
        OPERATIONS,
        "Deliver packages or food quickly, safely and with good service.",
        skills="route planning|safe driving|time management|customer service|package handling|"
        "using delivery apps|problem-solving|vehicle care",
        tools="delivery apps|GPS|handheld scanners|delivery vans|hand trucks",
        situations="a customer isn't home for a delivery that needs a signature|you're running late on your route|"
        "a package is damaged before delivery|a customer is rude about a late order|"
        "your vehicle breaks down mid-route|you can't find the address|"
        "a dog blocks the path to the door|the app sends you an impossible route",
        people="customers|dispatchers|warehouse staff|restaurant staff",
        metrics="on-time delivery rates|deliveries per hour|customer ratings|delivery errors",
    ),
    job(
        "production-supervisor",
        "Production Supervisor",
        OPERATIONS,
        "Lead a manufacturing team to hit safety, quality and output goals.",
        skills="team leadership|production scheduling|quality control|safety management|continuous improvement|"
        "root cause analysis|training workers|shift handoffs",
        tools="manufacturing execution systems|production boards|quality checklists|safety equipment|ERP systems",
        situations="a machine breakdown stops the line|the shift is short three workers|"
        "a batch fails quality inspection|a worker ignores safety rules|"
        "management raises output targets by 20%|two shifts blame each other for problems|"
        "an experienced worker resists a new process|a customer order is at risk of being late",
        people="production workers|maintenance teams|quality teams|plant managers",
        metrics="output per shift|defect rates|safety incidents|downtime",
    ),
    job(
        "quality-control-inspector",
        "Quality Control Inspector",
        OPERATIONS,
        "Check that products meet standards before they reach customers.",
        skills="inspection procedures|measurement and gauging|reading specifications|documenting defects|"
        "root cause analysis|statistical process control|communicating findings|attention to detail",
        tools="calipers and micrometers|gauges|inspection checklists|quality software|testing equipment",
        situations="you find a defect in a batch about to ship|production pressures you to pass borderline parts|"
        "measurements disagree between two gauges|a customer returns a batch you inspected|"
        "a supplier's parts keep failing inspection|you're unsure whether a defect is acceptable|"
        "a new product has unclear specifications|a coworker falsifies an inspection record",
        people="production teams|quality engineers|suppliers|supervisors",
        metrics="defect detection rates|customer returns|inspection times|first-pass yield",
    ),
    job(
        "procurement-specialist",
        "Procurement Specialist",
        OPERATIONS,
        "Buy goods and services at the right price, quality and time.",
        skills="supplier sourcing|negotiation|contract management|cost analysis|supplier relationship management|"
        "purchase order processing|risk management|compliance",
        tools="procurement software|ERP systems|spend analysis tools|contract databases|Excel",
        situations="a critical supplier goes out of business|a manager buys outside the approved process|"
        "a supplier raises prices 25%|a supplier offers you a personal gift|"
        "quality from a low-cost supplier is poor|a rush order needs a new supplier in days|"
        "a contract renewal is due and the supplier won't negotiate|internal teams disagree on which supplier to use",
        people="suppliers|internal requesters|finance teams|legal teams",
        metrics="cost savings|supplier on-time rates|contract compliance|purchase order cycle times",
    ),
]
