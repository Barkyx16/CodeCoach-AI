"""Business and finance, sales and marketing, and customer service and hospitality careers."""

from app.careers.profiles import job

FINANCE = "Business & Finance"
SALES = "Sales & Marketing"
SERVICE = "Customer Service & Hospitality"

JOBS = [
    job(
        "accountant",
        "Accountant",
        FINANCE,
        "Keep accurate financial records, close the books and make sure the numbers are right.",
        skills="account reconciliation|month-end close|financial reporting|tax compliance|accruals and journal entries|"
        "internal controls|budget variance analysis|explaining numbers to non-accountants",
        tools="accounting software|Excel|ERP systems|tax software|expense management tools",
        situations="the books don't balance the night before the close deadline|a manager asks you to book revenue early|"
        "you find a duplicate payment to a vendor|auditors request documents you can't find|"
        "a new accounting rule changes how you report|a department overspends its budget by 30%|"
        "an invoice looks like it could be fraudulent|you're asked to explain a big variance to executives",
        people="managers|auditors|vendors|finance leaders",
        metrics="days to close the books|reconciliation errors|audit findings|reporting deadlines met",
    ),
    job(
        "financial-analyst",
        "Financial Analyst",
        FINANCE,
        "Build forecasts and models that guide budgets and investment decisions.",
        skills="financial modeling|forecasting|variance analysis|valuation|presenting to executives|"
        "scenario planning|data gathering|building business cases",
        tools="Excel|financial planning software|SQL|PowerPoint|ERP systems",
        situations="your forecast misses by a wide margin|an executive challenges the assumptions in your model|"
        "you find an error in a model that has already been shared|a business unit refuses to share data|"
        "leadership wants a recommendation by tomorrow morning|two departments compete for the same budget|"
        "market conditions change right after you finish the annual plan|a project you supported loses money",
        people="executives|department heads|accountants|investors",
        metrics="forecast accuracy|budget variance|return on investment|time to produce reports",
    ),
    job(
        "bank-teller",
        "Bank Teller",
        FINANCE,
        "Handle deposits, withdrawals and customer questions accurately and securely.",
        skills="cash handling|customer service|fraud detection|balancing a cash drawer|explaining bank products|"
        "following compliance rules|accuracy under pressure|referring customers to specialists",
        tools="teller systems|cash counters|check scanners|identity verification tools|customer databases",
        situations="your cash drawer is short at the end of the day|a customer wants to withdraw a large sum and seems nervous|"
        "someone presents a check that looks altered|the line is out the door at lunchtime|"
        "a customer is angry about an overdraft fee|an elderly customer may be the victim of a scam|"
        "the system goes down mid-transaction|a customer asks you to skip an ID check because they're a regular",
        people="customers|branch managers|loan officers|security staff",
        metrics="cash drawer accuracy|customer wait times|product referrals|customer satisfaction scores",
    ),
    job(
        "loan-officer",
        "Loan Officer",
        FINANCE,
        "Help people and businesses get loans while managing the bank's risk.",
        skills="credit analysis|explaining loan options|document collection|regulatory compliance|relationship building|"
        "risk assessment|negotiation|pipeline management",
        tools="loan origination systems|credit reports|CRM software|underwriting guidelines|document portals",
        situations="a borrower's application is borderline|a customer is upset their loan was denied|"
        "a deal is about to close and a document is missing|a real estate agent pressures you to speed up approval|"
        "interest rates jump and your pipeline stalls|you suspect income documents are falsified|"
        "a long-time client asks for an exception to the rules|you have twice your normal number of applications",
        people="borrowers|underwriters|real estate agents|branch managers",
        metrics="loan volume|approval turnaround times|default rates|customer satisfaction scores",
    ),
    job(
        "auditor",
        "Auditor",
        FINANCE,
        "Check that financial records and controls are accurate and trustworthy.",
        skills="audit planning|testing controls|sampling|risk assessment|interviewing staff|documenting findings|"
        "professional skepticism|writing audit reports",
        tools="audit software|Excel|data analytics tools|document management systems|accounting systems",
        situations="a client is slow to provide the documents you need|you find a significant error near the deadline|"
        "a manager pressures you to soften a finding|the numbers look too perfect|"
        "a client employee seems to be hiding something|your audit team is short-staffed|"
        "the client changes accounting systems mid-year|you disagree with a senior auditor's conclusion",
        people="clients|audit managers|finance teams|audit committees",
        metrics="audit completion times|findings accepted|hours over budget|review notes received",
    ),
    job(
        "bookkeeper",
        "Bookkeeper",
        FINANCE,
        "Record transactions, pay bills and keep a small business's books in order.",
        skills="recording transactions|bank reconciliation|accounts payable|accounts receivable|payroll basics|"
        "organizing receipts|sales tax filing|reporting to owners",
        tools="QuickBooks|Excel|bank portals|receipt scanning apps|payroll software",
        situations="the bank balance doesn't match the books|a customer is ninety days late on a big invoice|"
        "the owner mixes personal and business expenses|a vendor says they were never paid|"
        "receipts for a whole month are missing|a tax deadline is two days away|"
        "the owner asks why profits are low when sales are up|you made a payroll mistake",
        people="business owners|vendors|customers|accountants",
        metrics="reconciliation accuracy|days sales outstanding|on-time bill payment|reporting timeliness",
    ),
    job(
        "investment-banking-analyst",
        "Investment Banking Analyst",
        FINANCE,
        "Build models and pitch materials for mergers, acquisitions and financing deals.",
        skills="financial modeling|valuation|pitch book preparation|industry research|due diligence|"
        "attention to detail|working under tight deadlines|presenting analysis",
        tools="Excel|PowerPoint|financial databases|data rooms|valuation models",
        situations="a managing director wants a revised model in two hours|you find a mistake in a deck already sent to a client|"
        "two deals need you on the same night|the client's numbers don't add up during due diligence|"
        "a deal falls apart after months of work|an associate gives you conflicting instructions|"
        "the market moves sharply on the day of a pitch|you're asked a question in a client meeting you can't answer",
        people="associates|managing directors|clients|lawyers",
        metrics="deals closed|model accuracy|turnaround times|client feedback",
    ),
    job(
        "insurance-agent",
        "Insurance Agent",
        FINANCE,
        "Help people choose the right insurance and support them when they file claims.",
        skills="needs assessment|explaining coverage|prospecting|policy comparison|claims support|"
        "handling objections|regulatory compliance|client retention",
        tools="CRM software|quoting systems|carrier portals|email marketing tools|policy management systems",
        situations="a client's claim is denied and they blame you|a prospect says insurance is a waste of money|"
        "a client wants coverage that doesn't fit their needs|premiums rise and clients threaten to leave|"
        "a client asks you to backdate a policy|you lose a big client to a competitor|"
        "a disaster hits and many clients file claims at once|a client doesn't understand their policy",
        people="clients|insurance carriers|claims adjusters|agency managers",
        metrics="policies sold|client retention rates|premium growth|customer satisfaction scores",
    ),
    job(
        "management-consultant",
        "Management Consultant",
        FINANCE,
        "Diagnose business problems and recommend changes that leaders can act on.",
        skills="problem structuring|hypothesis-driven analysis|client interviews|building slide decks|"
        "market sizing|stakeholder management|synthesizing findings|presenting recommendations",
        tools="Excel|PowerPoint|survey tools|data analysis tools|project management software",
        situations="the client's leadership disagrees with your findings|you have one week to answer a big strategic question|"
        "client staff won't share data with you|your analysis contradicts your manager's hypothesis|"
        "the project scope keeps growing|a client executive wants you to justify a decision they already made|"
        "your team member is struggling to deliver|a recommendation you made isn't working",
        people="client executives|engagement managers|client staff|partners",
        metrics="client satisfaction|projects delivered on time|recommendations adopted|follow-on work won",
    ),
    job(
        "operations-manager",
        "Operations Manager",
        FINANCE,
        "Run the day-to-day processes and people that keep a business delivering.",
        skills="process improvement|team leadership|scheduling and staffing|budget management|KPI tracking|"
        "vendor management|problem-solving|safety and compliance",
        tools="ERP systems|scheduling software|dashboards|spreadsheets|inventory systems",
        situations="a key supplier misses a delivery|two team leads are in open conflict|"
        "costs rise 15% and leadership wants them cut|a process change makes things slower|"
        "staff turnover doubles in one quarter|a safety incident happens on your watch|"
        "a big customer complains about late orders|you must roll out a new system with no extra staff",
        people="frontline staff|team leads|senior leadership|suppliers",
        metrics="on-time delivery rates|cost per unit|employee turnover|customer complaints",
    ),
    job(
        "payroll-specialist",
        "Payroll Specialist",
        FINANCE,
        "Pay everyone correctly and on time, and keep payroll compliant.",
        skills="payroll processing|tax withholding|benefits deductions|timekeeping review|payroll compliance|"
        "handling employee questions|confidentiality|year-end reporting",
        tools="payroll software|timekeeping systems|HR information systems|Excel|tax filing portals",
        situations="an employee was underpaid and needs money today|a payroll file fails to upload on payday|"
        "a manager approves overtime after the cutoff|tax rules change mid-year|"
        "an employee asks about a coworker's salary|you discover you overpaid someone for months|"
        "timecards are missing for a whole team|the company adds employees in a new state",
        people="employees|HR teams|managers|finance teams",
        metrics="payroll accuracy rates|on-time payroll runs|tax filing penalties|employee inquiries",
    ),
    job(
        "tax-preparer",
        "Tax Preparer",
        FINANCE,
        "Prepare accurate tax returns and help clients understand what they owe.",
        skills="tax return preparation|interviewing clients|document review|tax law research|deadline management|"
        "explaining tax concepts|accuracy checking|confidentiality",
        tools="tax software|client portals|IRS resources|Excel|document scanners",
        situations="a client brings a shoebox of receipts the week of the deadline|a client asks you to claim a deduction they don't qualify for|"
        "you find an error on a return you already filed|a client gets an IRS letter and panics|"
        "you have more returns than hours before the deadline|a client's records contradict what they told you|"
        "tax software crashes during peak season|a client is angry they owe money",
        people="clients|tax authorities|senior preparers|financial advisors",
        metrics="return accuracy|returns filed on time|client retention|amended returns",
    ),
    # Sales & Marketing
    job(
        "sales-representative",
        "Sales Representative",
        SALES,
        "Find prospects, understand their needs and close deals.",
        skills="prospecting|discovery questions|handling objections|product demos|negotiation|closing|"
        "pipeline management|follow-up",
        tools="CRM software|email outreach tools|video call platforms|LinkedIn|quoting tools",
        situations="you're far behind your quota with two weeks left|a prospect says your price is too high|"
        "a deal you counted on goes silent|a customer asks for a feature you don't have|"
        "a competitor offers a big discount|a prospect asks you to bend the contract rules|"
        "your biggest customer threatens to cancel|you get a lead in an industry you know nothing about",
        people="prospects|existing customers|sales managers|product teams",
        metrics="quota attainment|win rates|pipeline value|average deal size",
    ),
    job(
        "account-executive",
        "Account Executive",
        SALES,
        "Own large deals from first meeting to signed contract.",
        skills="discovery|building a business case|multi-stakeholder selling|negotiation|forecasting|"
        "presenting to executives|account planning|closing",
        tools="CRM software|sales engagement platforms|contract tools|video call platforms|forecasting tools",
        situations="a champion at your top account leaves the company|procurement demands a 30% discount|"
        "legal review delays a deal past quarter end|a demo goes badly in front of executives|"
        "your forecast deal slips to next quarter|a customer wants a custom contract term|"
        "two decision-makers want different things|a competitor is already embedded in the account",
        people="buyers|sales engineers|sales managers|legal teams",
        metrics="quota attainment|forecast accuracy|sales cycle length|win rates",
    ),
    job(
        "marketing-manager",
        "Marketing Manager",
        SALES,
        "Plan campaigns that build awareness, generate demand and grow revenue.",
        skills="campaign planning|market research|budget management|messaging and positioning|team leadership|"
        "performance analysis|channel strategy|cross-team collaboration",
        tools="marketing automation platforms|analytics tools|CRM software|ad platforms|project management tools",
        situations="a campaign launches and results are far below target|sales says marketing leads are low quality|"
        "your budget is cut by 40% mid-quarter|a competitor launches a copycat campaign|"
        "a social media post causes public backlash|leadership wants results in one month|"
        "your team misses a launch deadline|the data shows your favorite channel isn't working",
        people="sales teams|executives|creative teams|agencies",
        metrics="leads generated|cost per acquisition|campaign return on investment|brand awareness",
    ),
    job(
        "digital-marketing-specialist",
        "Digital Marketing Specialist",
        SALES,
        "Run online ads, email and content that bring in customers.",
        skills="paid advertising|email marketing|conversion optimization|audience targeting|A/B testing|"
        "analytics reporting|content scheduling|budget pacing",
        tools="Google Ads|Meta Ads Manager|email platforms|Google Analytics|landing page builders",
        situations="ad costs suddenly double|an email goes out with a broken link to 100,000 people|"
        "conversions drop after a website change|your boss wants results from a channel that isn't working|"
        "an ad account is suspended|tracking breaks and you can't measure results|"
        "you must launch a campaign in 48 hours|an A/B test result looks too good to be true",
        people="marketing managers|designers|web developers|sales teams",
        metrics="cost per click|conversion rates|email open rates|return on ad spend",
    ),
    job(
        "social-media-manager",
        "Social Media Manager",
        SALES,
        "Build a brand's voice and community across social platforms.",
        skills="content planning|community management|copywriting|trend spotting|analytics|"
        "crisis response|influencer partnerships|visual storytelling",
        tools="social scheduling tools|Instagram|TikTok|LinkedIn|analytics dashboards",
        situations="a post goes viral for the wrong reasons|engagement falls for three months straight|"
        "a customer complaint blows up in the comments|leadership wants to join a trend that doesn't fit the brand|"
        "an influencer partner posts something offensive|you have no budget for paid promotion|"
        "an algorithm change cuts your reach in half|legal must approve every post and it slows you down",
        people="followers|marketing teams|customer support teams|influencers",
        metrics="engagement rates|follower growth|reach|social media referral traffic",
    ),
    job(
        "content-writer",
        "Content Writer",
        SALES,
        "Write articles, guides and copy that inform readers and support a brand.",
        skills="research|writing for an audience|editing|SEO writing|interviewing experts|meeting deadlines|"
        "adapting tone|taking feedback",
        tools="Google Docs|content management systems|SEO tools|grammar checkers|project trackers",
        situations="an editor sends back heavy edits on your draft|you're assigned a topic you know nothing about|"
        "three deadlines land on the same day|a source won't respond before your deadline|"
        "your article gets very little traffic|a client wants the content rewritten in a different voice|"
        "you find out a fact in your published article was wrong|you're asked to write something you think is misleading",
        people="editors|clients|subject-matter experts|readers",
        metrics="organic traffic|time on page|deadlines met|content conversions",
    ),
    job(
        "seo-specialist",
        "SEO Specialist",
        SALES,
        "Help a website rank higher in search results and bring in more visitors.",
        skills="keyword research|technical SEO audits|on-page optimization|link building|content strategy|"
        "analytics reporting|site migrations|explaining SEO to stakeholders",
        tools="Google Search Console|Google Analytics|SEO crawlers|keyword research tools|content management systems",
        situations="organic traffic drops 30% overnight|a site redesign launches without redirects|"
        "a stakeholder wants number-one rankings in a month|a competitor outranks you on your main keyword|"
        "developers can't prioritize your technical fixes|a search algorithm update hits your rankings|"
        "duplicate pages are competing with each other|leadership asks why SEO results take so long",
        people="content writers|web developers|marketing managers|executives",
        metrics="organic traffic|keyword rankings|click-through rates|organic conversions",
        role="SEO specialist",
    ),
    job(
        "brand-manager",
        "Brand Manager",
        SALES,
        "Shape how customers see a product or company and keep the brand consistent.",
        skills="brand strategy|consumer insights|product positioning|campaign management|budget management|"
        "cross-team leadership|packaging and design direction|competitive analysis",
        tools="market research reports|brand guidelines|project management tools|sales data|survey tools",
        situations="a competitor launches a similar product at a lower price|sales of your product drop for two quarters|"
        "a packaging change confuses loyal customers|a retailer wants a big promotion that hurts the brand|"
        "the brand faces negative news coverage|research shows customers misunderstand the brand|"
        "your agency delivers work that misses the brief|leadership wants to extend the brand into an unrelated product",
        people="consumers|sales teams|creative agencies|retail partners",
        metrics="market share|brand awareness|sales growth|customer loyalty",
    ),
    job(
        "real-estate-agent",
        "Real Estate Agent",
        SALES,
        "Help people buy and sell homes and guide them through every step.",
        skills="pricing homes|negotiation|marketing listings|client communication|market knowledge|"
        "contract management|lead generation|showing properties",
        tools="MLS listings|CRM software|e-signature tools|social media|photography and virtual tours",
        situations="a buyer's financing falls through a week before closing|a seller insists on a price that's too high|"
        "your buyer loses five bidding wars in a row|an inspection finds a major problem|"
        "a client wants you to hide a known defect|a listing gets no offers for two months|"
        "two clients want the same house|a deal is falling apart over a small repair",
        people="buyers|sellers|lenders|other agents",
        metrics="homes sold|days on market|sale-to-list price ratios|client referrals",
    ),
    job(
        "retail-sales-associate",
        "Retail Sales Associate",
        SALES,
        "Help shoppers find what they need and keep the store running smoothly.",
        skills="customer greeting|product knowledge|upselling|handling returns|visual merchandising|"
        "cash register operation|teamwork|loss prevention awareness",
        tools="point-of-sale systems|inventory scanners|store apps|price tag printers|payment terminals",
        situations="a customer wants to return an item without a receipt|the store is packed and you're the only one on the floor|"
        "a customer is rude to you|you think you see someone shoplifting|"
        "a customer asks for a product that's out of stock|your manager asks you to stay late again|"
        "the register shows the wrong price|a customer can't decide and keeps asking questions",
        people="customers|store managers|coworkers|loss prevention staff",
        metrics="sales per hour|average transaction value|customer satisfaction scores|shrink rates",
    ),
    # Customer Service & Hospitality
    job(
        "customer-service-representative",
        "Customer Service Representative",
        SERVICE,
        "Solve customers' problems by phone, chat or email and keep them happy.",
        skills="active listening|de-escalation|problem-solving|product knowledge|clear writing|"
        "following policy|empathy|documenting interactions",
        tools="help desk software|CRM systems|live chat tools|phone systems|knowledge bases",
        situations="a customer is yelling and demanding a manager|you don't know the answer to a customer's question|"
        "a customer asks for a refund that policy doesn't allow|the queue is twice as long as usual|"
        "a customer has contacted support five times about the same issue|a product outage floods support with tickets|"
        "a customer shares sensitive personal information|you made a mistake on a customer's account",
        people="customers|team leads|technical support teams|billing teams",
        metrics="customer satisfaction scores|first-contact resolution rates|average handle times|ticket backlogs",
    ),
    job(
        "call-center-agent",
        "Call Center Agent",
        SERVICE,
        "Handle a high volume of customer calls quickly and helpfully.",
        skills="call handling|following scripts|de-escalation|multitasking|accurate data entry|"
        "staying calm under pressure|meeting call targets|escalating correctly",
        tools="phone systems|CRM software|call scripts|knowledge bases|quality monitoring tools",
        situations="a caller is abusive|your call time is well above target|a caller needs something your script doesn't cover|"
        "the system freezes during a call|a caller is crying and upset|"
        "back-to-back difficult calls wear you down|a caller asks you to break policy just this once|"
        "a supervisor gives you negative feedback on a call",
        people="callers|supervisors|quality analysts|other departments",
        metrics="average handle times|calls resolved|quality scores|customer satisfaction scores",
    ),
    job(
        "restaurant-server",
        "Restaurant Server",
        SERVICE,
        "Take orders, serve food and give guests a great dining experience.",
        skills="guest service|menu knowledge|order accuracy|managing multiple tables|upselling|"
        "food safety|teamwork with the kitchen|handling complaints",
        tools="point-of-sale systems|order pads|payment terminals|reservation systems|table management apps",
        situations="a guest sends their food back twice|the kitchen is backed up and your tables are getting impatient|"
        "a guest has a severe food allergy|a large party arrives without a reservation|"
        "a guest leaves without paying|you spill a drink on a guest|"
        "a coworker isn't pulling their weight on a busy night|a guest is rude to you in front of other tables",
        people="guests|kitchen staff|managers|bussers and hosts",
        metrics="table turn times|average check size|guest satisfaction|order errors",
        role="server",
    ),
    job(
        "bartender",
        "Bartender",
        SERVICE,
        "Make drinks, serve guests and keep the bar safe and fun.",
        skills="drink preparation|responsible alcohol service|guest service|speed under pressure|cash handling|"
        "inventory and stock|upselling|keeping the bar clean",
        tools="point-of-sale systems|bar tools|inventory sheets|ID scanners|payment terminals",
        situations="a guest is clearly intoxicated and wants another drink|the bar is three deep and you're alone|"
        "a guest uses an ID that looks fake|two guests start arguing|"
        "your till is short at the end of the night|a guest says their drink is wrong|"
        "you run out of a popular ingredient|a coworker gives free drinks to friends",
        people="guests|managers|servers|security staff",
        metrics="sales per shift|drink waste|guest satisfaction|pour accuracy",
    ),
    job(
        "hotel-front-desk-agent",
        "Hotel Front Desk Agent",
        SERVICE,
        "Check guests in and out and solve problems during their stay.",
        skills="check-in and check-out|reservation management|guest problem-solving|upselling rooms|"
        "handling payments|local knowledge|calm communication|security procedures",
        tools="property management systems|key card encoders|payment terminals|phone systems|booking platforms",
        situations="the hotel is overbooked and a guest has nowhere to stay|a guest complains their room is dirty|"
        "a guest asks for another guest's room number|a long line forms at check-in|"
        "a guest's card is declined|a guest reports a noisy neighbor at 2 a.m.|"
        "the booking system goes down|a guest asks for a refund for their whole stay",
        people="guests|housekeeping staff|managers|maintenance staff",
        metrics="check-in times|guest satisfaction scores|upgrade revenue|online review ratings",
    ),
    job(
        "line-cook",
        "Line Cook",
        SERVICE,
        "Prepare dishes quickly and consistently on a busy kitchen line.",
        skills="knife skills|food safety|prep work|cooking to standard|speed and timing|keeping a clean station|"
        "following recipes|communicating on the line",
        tools="commercial ovens and grills|knives|thermometers|ticket printers|prep lists",
        situations="tickets pile up during the dinner rush|you run out of a key ingredient mid-service|"
        "a dish is sent back as undercooked|a coworker calls out sick on a Saturday|"
        "you see a coworker skip food safety steps|the chef criticizes your plating in front of everyone|"
        "an allergy ticket comes through during the rush|equipment breaks in the middle of service",
        people="chefs|servers|other cooks|dishwashers",
        metrics="ticket times|food waste|dish consistency|health inspection scores",
    ),
    job(
        "barista",
        "Barista",
        SERVICE,
        "Make great coffee drinks and give every customer friendly, fast service.",
        skills="espresso preparation|milk steaming|customer service|speed during rushes|order accuracy|"
        "cleanliness|cash handling|teamwork",
        tools="espresso machines|grinders|point-of-sale systems|mobile order tablets|blenders",
        situations="the morning rush hits and mobile orders keep coming|a customer says their drink is wrong|"
        "the espresso machine breaks down|a regular wants a drink made a way that's against policy|"
        "you're out of a popular milk|a customer is rude about the wait|"
        "a coworker is always late to their shift|a customer leaves a complaint online",
        people="customers|shift supervisors|coworkers|store managers",
        metrics="drink times|order accuracy|customer satisfaction|waste",
    ),
    job(
        "restaurant-manager",
        "Restaurant Manager",
        SERVICE,
        "Lead the staff, guests and numbers of a restaurant.",
        skills="staff scheduling|hiring and training|guest recovery|cost control|food safety compliance|"
        "inventory management|team motivation|conflict resolution",
        tools="scheduling software|point-of-sale reports|inventory systems|reservation systems|payroll systems",
        situations="three staff call out on a Friday night|food costs rise 20% in a month|"
        "a guest posts a scathing online review|a health inspector arrives unannounced|"
        "two employees have a heated conflict during service|your best server gives notice|"
        "the owner wants labor costs cut|a guest gets sick and blames your food",
        people="guests|servers and cooks|owners|suppliers",
        metrics="labor cost percentages|food cost percentages|guest satisfaction|staff turnover",
    ),
    job(
        "flight-attendant",
        "Flight Attendant",
        SERVICE,
        "Keep passengers safe and comfortable from boarding to landing.",
        skills="safety procedures|passenger service|emergency response|de-escalation|teamwork with the crew|"
        "cabin announcements|attention to detail|staying calm under pressure",
        tools="safety equipment|first aid kits|cabin service carts|crew communication systems|inflight entertainment systems",
        situations="a passenger refuses to follow a crew instruction|a passenger has a medical emergency mid-flight|"
        "the flight is delayed for hours on the tarmac|a passenger is drunk and disruptive|"
        "there's turbulence during meal service|a passenger complains about their seat|"
        "a crew member seems unwell on duty|a passenger is very afraid of flying",
        people="passengers|pilots|other flight attendants|ground staff",
        metrics="on-time departures|passenger satisfaction|safety compliance|incident reports",
    ),
    job(
        "event-planner",
        "Event Planner",
        SERVICE,
        "Plan and run events so every detail is on time and on budget.",
        skills="budget management|vendor coordination|timeline planning|negotiation|on-site problem-solving|"
        "client communication|logistics|risk planning",
        tools="event management software|spreadsheets|contracts|floor plan tools|registration platforms",
        situations="the venue cancels two weeks before the event|the client changes the theme last minute|"
        "a vendor doesn't show up on the day|attendance is half of what you expected|"
        "the budget runs out before everything is booked|bad weather threatens an outdoor event|"
        "a speaker is stuck in an airport|a guest has a medical emergency at the event",
        people="clients|vendors|venue staff|attendees",
        metrics="events delivered on budget|attendee satisfaction|vendor costs|repeat clients",
    ),
]
