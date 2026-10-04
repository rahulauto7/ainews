"""Every source the scraper reads, and the section each one feeds. Data only.

The keyless rule (2026-10-02): every section searches every platform that can be
read WITHOUT an API key. A platform that needs one is skipped, even when a key
sits in .env - the X API, the YouTube Data API and NewsAPI are all out. X has no
keyless feed, so the "on X" rows below are Google News searches of the posts
Google has indexed; that partial coverage is accepted.

RSS   = [(name, url, category, flags)]
EXTRA = [(name, category, kind, arg)]   non-RSS readers, run by scrape_rss_feeds.EXTRA_READERS

category  the digest group, which names the PDF section the source mainly feeds.
          news_digest.CATEGORY_ORDER maps each group to its section.
flags     space-separated, "" for none:
            ai       general-interest feed: keep only entries that mention AI
            musk     keep only entries where Musk talks about AI or autonomy
            browser  the site refuses the bot User-Agent: send the browser one
            top      keep only the feed's first 20 entries (regional Google News
                     editions return 100 each)

Names are keys elsewhere: scrape_rss_feeds.window_hours_for() and the tests look
some up, and "arXiv ..." names keep the 15-per-feed cap. Rename with care.

A trailing "# live" means the source works but posts less than daily; "# new-query"
means the query text had not been run when it was added (2 Oct 2026), so drop or
fix it if the first scrapes return nothing. The rejected list at the end of this
file is every source tested and turned down: do not retry those.
"""

RSS = [
    # --- opportunity (30-day lookback) -> AI Hackathons / AI Grants, Fellowships & Programs
    # These are things a reader can ENTER or APPLY TO, not news about them, so the
    # feed has to reach back much further than a day: a hackathon closing in three
    # weeks was announced last month. Google News search queries were the only
    # sources that returned entrants when probed (57 / 17 / 6 / 74 entries).
    ('AI Hackathons (via Google News)', 'https://news.google.com/rss/search?q=%22AI+hackathon%22+OR+%22hackathon%22+(AI+OR+%22artificial+intelligence%22+OR+%22machine+learning%22)+when:30d&hl=en-US&gl=US&ceid=US:en', 'opportunity', ''),
    ('AI Competitions (via Google News)', 'https://news.google.com/rss/search?q=(%22AI+challenge%22+OR+%22AI+competition%22+OR+%22AI+contest%22)+(prize+OR+submissions+OR+registration+OR+deadline)+when:30d&hl=en-US&gl=US&ceid=US:en', 'opportunity', ''),
    ('AI Programs (via Google News)', 'https://news.google.com/rss/search?q=(%22AI+accelerator+program%22+OR+%22AI+incubator%22+OR+%22AI+fellowship%22+OR+%22AI+residency%22)+(applications+OR+cohort+OR+apply)+when:30d&hl=en-US&gl=US&ceid=US:en', 'opportunity', ''),
    ('AI Applications Open (via Google News)', 'https://news.google.com/rss/search?q=(%22applications+open%22+OR+%22apply+now%22+OR+%22call+for+applications%22)+(AI+OR+%22artificial+intelligence%22)+(program+OR+cohort+OR+accelerator+OR+grant+OR+hackathon)+when:30d&hl=en-US&gl=US&ceid=US:en', 'opportunity', ''),
    ('AI Grants (via Google News)', 'https://news.google.com/rss/search?q=(%22AI+grant%22+OR+%22AI+grants%22+OR+%22AI+fund%22)+(apply+OR+applications+OR+deadline)+when:30d&hl=en-US&gl=US&ceid=US:en', 'opportunity', ''),
    ('AI Hackathons (via Bing News)', 'https://www.bing.com/news/search?q=AI+hackathon&format=rss', 'opportunity', 'browser'),

    # --- careers -> Remote FDE & Solutions Jobs (2026-10-03). rahul's goal is a remote or
    # visa-sponsored Forward Deployed / Solutions Engineer role at a global company: news
    # about those roles, AI hiring, work visas and remote work. The section's open-roles
    # table comes from tools/find_roles.py, not from these feeds.
    ('Forward deployed engineers (via Google News)', 'https://news.google.com/rss/search?q=%22forward+deployed+engineer%22+OR+%22forward+deployed+engineers%22+OR+%22forward-deployed+engineer%22+OR+%22forward-deployed+engineers%22+OR+%22forward+deployed+engineering%22+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'careers', ''),
    ('Solutions engineers in AI (via Google News)', 'https://news.google.com/rss/search?q=%28%22solutions+engineer%22+OR+%22solutions+engineers%22+OR+%22solutions+architect%22+OR+%22sales+engineer%22+OR+%22customer+engineer%22%29+%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'careers', ''),
    ('AI deployment jobs (via Google News)', 'https://news.google.com/rss/search?q=%28%22applied+AI+engineer%22+OR+%22deployment+engineer%22+OR+%22AI+deployment%22+OR+%22deployment+strategist%22%29+%28hiring+OR+jobs+OR+team+OR+engineers%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'careers', ''),
    ('Tech work visas (via Google News)', 'https://news.google.com/rss/search?q=%28%22H-1B%22+OR+%22skilled+worker+visa%22+OR+%22Global+Talent+visa%22+OR+%22O-1+visa%22+OR+%22Blue+Card%22+OR+%22tech+visa%22%29+%28tech+OR+AI+OR+engineers+OR+software%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'careers', ''),
    ('Remote tech hiring (via Google News)', 'https://news.google.com/rss/search?q=%28%22remote+work%22+OR+%22remote+jobs%22+OR+%22remote+hiring%22+OR+%22return+to+office%22+OR+%22work+from+anywhere%22%29+%28tech+OR+AI+OR+software+OR+engineers%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'careers', ''),
    ('AI talent market (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+%28%22talent+war%22+OR+%22hiring+spree%22+OR+%22AI+engineers%22+OR+%22AI+jobs%22%29+%28salary+OR+hiring+OR+pay%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'careers', ''),
    ('Forward deployed engineers (via Bing News)', 'https://www.bing.com/news/search?q=%22forward+deployed+engineer%22&format=rss', 'careers', 'browser'),

    # --- rsi -> AI Self-Improvement (RSI)
    ('AI Self-Improvement (via Google News)', 'https://news.google.com/rss/search?q=(%22recursive+self-improvement%22+OR+%22self-improving+AI%22+OR+%22AI+alignment%22+OR+superintelligence+OR+AGI)+when:1d&hl=en-US&gl=US&ceid=US:en', 'rsi', ''),
    ('Alignment Forum', 'https://www.alignmentforum.org/feed.xml', 'rsi', ''),
    ('LessWrong', 'https://www.lesswrong.com/feed.xml?view=frontpage-rss&karmaThreshold=75', 'rsi', 'ai'),
    ('METR', 'https://metr.org/feed.xml', 'rsi', ''),  # live
    ('Redwood Research', 'https://blog.redwoodresearch.org/feed', 'rsi', ''),  # live
    ('AI Safety Newsletter', 'https://newsletter.safe.ai/feed', 'rsi', ''),  # live
    ('Epoch AI Gradient Updates', 'https://epochai.substack.com/feed', 'rsi', ''),  # live
    ('80,000 Hours', 'https://80000hours.org/feed/', 'rsi', 'ai'),
    ('Future of Life Institute', 'https://futureoflife.org/feed/', 'rsi', 'ai'),  # live
    ('Zvi Mowshowitz', 'https://thezvi.substack.com/feed', 'rsi', ''),
    ('Transformer News', 'https://www.transformernews.ai/feed', 'rsi', ''),
    ('AI as Normal Technology', 'https://www.normaltech.ai/feed', 'rsi', ''),
    # Added 2026-10-03 ("search everywhere on the internet"):
    ('AI Safety (via Bing News)', 'https://www.bing.com/news/search?q=AI+safety+alignment&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'rsi', 'browser'),

    # --- ai_research -> AI Self-Improvement (RSI) and leads for other sections. Names starting "arXiv" keep the 15-per-feed cap.
    ('arXiv AI', 'https://rss.arxiv.org/rss/cs.AI', 'ai_research', ''),
    ('arXiv Machine Learning', 'https://rss.arxiv.org/rss/cs.LG', 'ai_research', ''),
    ('arXiv Computation and Language', 'https://rss.arxiv.org/rss/cs.CL', 'ai_research', ''),
    ('arXiv Multiagent Systems', 'https://rss.arxiv.org/rss/cs.MA', 'ai_research', ''),
    ('Apple Machine Learning Research', 'https://machinelearning.apple.com/rss.xml', 'ai_research', ''),
    ('Microsoft Research', 'https://www.microsoft.com/en-us/research/feed/', 'ai_research', 'ai'),  # live
    ('Amazon Science', 'https://www.amazon.science/index.rss', 'ai_research', 'ai'),  # live
    ('Nature Machine Intelligence', 'https://www.nature.com/natmachintell.rss', 'ai_research', ''),  # live
    ('MIT News AI', 'https://news.mit.edu/rss/topic/artificial-intelligence2', 'ai_research', ''),
    ('TechXplore AI', 'https://techxplore.com/rss-feed/machine-learning-ai-news/', 'ai_research', ''),
    ('phys.org AI', 'https://phys.org/rss-feed/technology-news/machine-learning-ai/', 'ai_research', ''),
    ('ScienceDaily AI', 'https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml', 'ai_research', ''),  # live
    ('Quanta Magazine', 'https://www.quantamagazine.org/feed/', 'ai_research', 'ai'),
    # Science explainers, added 2026-10-03: written for readers with no background,
    # which is what every summary now has to do.
    ('The Conversation AI', 'https://theconversation.com/global/topics/artificial-intelligence-ai-90/articles.atom', 'ai_research', ''),
    ('New Scientist Technology', 'https://www.newscientist.com/subject/technology/feed/', 'ai_research', 'ai'),
    ('Nature News', 'https://www.nature.com/nature.rss', 'ai_research', 'ai'),
    ('Science News', 'https://www.sciencenews.org/feed', 'ai_research', 'ai'),
    ('Science Magazine News', 'https://www.science.org/rss/news_current.xml', 'ai_research', 'ai'),
    ('Big Think', 'https://bigthink.com/feed/', 'ai_research', 'ai'),  # live
    ('Sakana AI', 'https://sakana.ai/feed.xml', 'ai_research', ''),  # live
    ('AI Research (via Bing News)', 'https://www.bing.com/news/search?q=AI+research+breakthrough&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'ai_research', 'browser'),

    # --- quantum (7-day rule, Thursdays only) -> Quantum + AI
    # The arXiv RSS feed only ever carries a SINGLE day of papers (verified
    # 2026-09-03: all 143 entries shared one date), so widening the cutoff on it
    # retrieves nothing older. Real 7-day coverage comes from the Google News
    # proxy below, using the same when:Nd trick already proven on the Musk and
    # Anthropic feeds. The arXiv API (export.arxiv.org) was tried first and is
    # not usable here - it returned HTTP 429 on every attempt.
    ('arXiv Quantum Physics', 'https://rss.arxiv.org/rss/quant-ph', 'quantum', ''),
    ('Quantum + AI (via Google News)', 'https://news.google.com/rss/search?q=(quantum+computing+OR+quantum+machine+learning)+(AI+OR+%22machine+learning%22+OR+%22neural+network%22)+when:7d&hl=en-US&gl=US&ceid=US:en', 'quantum', ''),
    ('The Quantum Insider', 'https://thequantuminsider.com/feed/', 'quantum', 'ai'),
    ('Quantum Computing Report', 'https://quantumcomputingreport.com/feed/', 'quantum', 'ai'),
    ('Quantum Zeitgeist', 'https://quantumzeitgeist.com/feed/', 'quantum', 'ai'),
    ('phys.org Quantum', 'https://phys.org/rss-feed/physics-news/quantum-physics/', 'quantum', 'ai'),

    # --- problems -> Unaddressed AI Problems
    ('AI Problems (via Google News)', 'https://news.google.com/rss/search?q=AI+(fails+OR+failure+OR+flaw+OR+%22struggles+with%22+OR+limitation+OR+hallucination+OR+unsolved+OR+%22no+solution%22)+when:1d&hl=en-US&gl=US&ceid=US:en', 'problems', ''),
    ('AI Incident Database', 'https://incidentdatabase.ai/rss.xml', 'problems', ''),  # live
    ('404 Media', 'https://www.404media.co/rss/', 'problems', 'ai'),
    ('Marcus on AI', 'https://garymarcus.substack.com/feed', 'problems', ''),  # live
    # Added 2026-10-03: AI security incidents and AI's critics.
    ('The Hacker News', 'https://feeds.feedburner.com/TheHackersNews', 'problems', 'ai'),
    ('BleepingComputer', 'https://www.bleepingcomputer.com/feed/', 'problems', 'ai'),
    ('Dark Reading', 'https://www.darkreading.com/rss.xml', 'problems', 'ai'),
    ('SecurityWeek', 'https://www.securityweek.com/feed/', 'problems', 'ai'),
    ('EFF Deeplinks', 'https://www.eff.org/rss/updates.xml', 'problems', 'ai'),
    ('AI Now Institute', 'https://ainowinstitute.org/feed', 'problems', ''),  # live
    ('Pivot to AI', 'https://pivot-to-ai.com/feed/', 'problems', ''),
    ("Where's Your Ed At", 'https://www.wheresyoured.at/feed', 'problems', ''),  # live
    ('AI Problems (via Bing News)', 'https://www.bing.com/news/search?q=AI+failure+OR+AI+problem&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'problems', 'browser'),

    # --- automation -> AI Automation & Business
    ('AI Automation (via Google News)', 'https://news.google.com/rss/search?q=(%22AI+automation%22+OR+%22AI+agents%22+OR+%22agentic+AI%22+OR+%22workflow+automation%22)+when:1d&hl=en-US&gl=US&ceid=US:en', 'automation', ''),
    ('Zapier Blog', 'https://zapier.com/blog/feeds/latest/', 'automation', 'ai'),
    ('n8n Blog', 'https://blog.n8n.io/rss/', 'automation', ''),  # live
    ('UiPath Blog', 'https://www.uipath.com/blog/rss.xml', 'automation', 'ai'),  # live
    ('Salesforce News', 'https://www.salesforce.com/news/feed/', 'automation', 'ai'),
    ('Databricks Blog', 'https://www.databricks.com/feed', 'automation', 'ai'),
    ('Cloudflare Blog', 'https://blog.cloudflare.com/rss/', 'automation', 'ai'),
    ('GitHub Blog AI', 'https://github.blog/ai-and-ml/feed/', 'automation', ''),
    ('Stack Overflow Blog', 'https://stackoverflow.blog/feed/', 'automation', 'ai'),
    ('AWS Machine Learning Blog', 'https://aws.amazon.com/blogs/machine-learning/feed/', 'automation', ''),
    ('The New Stack', 'https://thenewstack.io/feed/', 'automation', 'ai'),
    ('InfoWorld AI', 'https://www.infoworld.com/artificial-intelligence/feed/', 'automation', ''),
    ('CIO AI', 'https://www.cio.com/artificial-intelligence/feed/', 'automation', ''),
    ('Computerworld AI', 'https://www.computerworld.com/artificial-intelligence/feed/', 'automation', ''),
    ('AI Business', 'https://aibusiness.com/rss.xml', 'automation', ''),
    ('KDnuggets', 'https://www.kdnuggets.com/feed', 'automation', 'ai'),
    ('Analytics Vidhya', 'https://www.analyticsvidhya.com/feed/', 'automation', 'ai'),  # live
    # Added 2026-10-03: enterprise and developer trade press.
    ('InfoQ AI', 'https://feed.infoq.com/ai-ml-data-eng/', 'automation', ''),
    ('Dataconomy', 'https://dataconomy.com/feed/', 'automation', 'ai'),
    ('eWeek AI', 'https://www.eweek.com/artificial-intelligence/feed/', 'automation', ''),
    ('CRN', 'https://www.crn.com/news/rss.xml', 'automation', 'ai'),
    ('Computer Weekly', 'https://www.computerweekly.com/rss/All-Computer-Weekly-content.xml', 'automation', 'ai'),
    ('ITPro', 'https://www.itpro.com/feeds/all', 'automation', 'ai'),
    ('Techstrong AI', 'https://techstrong.ai/feed/', 'automation', ''),
    ('DevOps.com', 'https://devops.com/feed/', 'automation', 'ai'),
    ('The Next Platform', 'https://www.nextplatform.com/feed/', 'automation', 'ai'),  # live
    ('The Pragmatic Engineer', 'https://newsletter.pragmaticengineer.com/feed', 'automation', 'ai'),  # live
    ("Lenny's Newsletter", 'https://www.lennysnewsletter.com/feed', 'automation', 'ai'),  # live
    ('AI Automation (via Bing News)', 'https://www.bing.com/news/search?q=AI+agents+automation&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'automation', 'browser'),

    # --- business -> AI Business Opportunities
    ('AI Funding (via Google News)', 'https://news.google.com/rss/search?q=AI+startup+(raises+OR+funding+OR+valuation+OR+%22Series+A%22+OR+%22seed+round%22)+when:1d&hl=en-US&gl=US&ceid=US:en', 'business', ''),
    ('Crunchbase News', 'https://news.crunchbase.com/feed/', 'business', 'ai'),
    ('TechCrunch Startups', 'https://techcrunch.com/category/startups/feed/', 'business', 'ai'),
    ('TechCrunch Venture', 'https://techcrunch.com/category/venture/feed/', 'business', 'ai'),
    ('AlleyWatch', 'https://www.alleywatch.com/feed/', 'business', 'ai'),
    ('Sifted', 'https://sifted.eu/feed', 'business', 'ai'),
    ('Tech.eu', 'https://tech.eu/feed/', 'business', 'ai'),
    # Added 2026-10-03: business and markets press.
    ('Inc', 'https://www.inc.com/rss', 'business', 'ai'),
    ('Entrepreneur', 'https://www.entrepreneur.com/latest.rss', 'business', 'ai'),
    ('MarketWatch', 'https://feeds.content.dowjones.io/public/rss/mw_topstories', 'business', 'ai'),
    ('Benzinga', 'https://www.benzinga.com/feed', 'business', 'ai'),
    ('Noahpinion', 'https://www.noahpinion.blog/feed', 'business', 'ai'),  # live
    ('AI Funding (via Bing News)', 'https://www.bing.com/news/search?q=AI+startup+funding&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'business', 'browser'),

    # --- showcase -> AI Business Opportunities
    ('Product Hunt AI', 'https://www.producthunt.com/feed?category=artificial-intelligence', 'showcase', ''),
    ('Product Hunt', 'https://www.producthunt.com/feed', 'showcase', 'ai'),

    # --- indian -> Indian AI Industry
    ('Inc42', 'https://inc42.com/feed/', 'indian', 'ai'),
    ('YourStory', 'https://yourstory.com/feed', 'indian', 'ai'),
    ('Economic Times Tech', 'https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms', 'indian', 'ai'),
    ('India AI (via Google News)', 'https://news.google.com/rss/search?q=(AI+OR+%22artificial+intelligence%22)+(India+OR+Indian)+when:1d&hl=en-IN&gl=IN&ceid=IN:en', 'indian', ''),
    ('Mint AI', 'https://www.livemint.com/rss/AI', 'indian', ''),
    ('Mint Technology', 'https://www.livemint.com/rss/technology', 'indian', 'ai'),
    ('Business Standard Technology', 'https://www.business-standard.com/rss/technology-108.rss', 'indian', 'ai'),
    ('The Hindu Technology', 'https://www.thehindu.com/sci-tech/technology/feeder/default.rss', 'indian', 'ai'),
    ('Indian Express AI', 'https://indianexpress.com/section/technology/artificial-intelligence/feed/', 'indian', ''),
    ('Hindustan Times Tech', 'https://www.hindustantimes.com/feeds/rss/technology/rssfeed.xml', 'indian', 'ai'),
    ('MediaNama', 'https://www.medianama.com/feed/', 'indian', 'ai'),  # live
    ('Entrackr', 'https://entrackr.com/rss', 'indian', 'ai'),  # live
    ('The Ken', 'https://the-ken.com/feed/', 'indian', 'ai'),
    # Added 2026-10-03.
    ('Economic Times AI', 'https://economictimes.indiatimes.com/tech/artificial-intelligence/rssfeeds/119215726.cms', 'indian', ''),
    ('India Today Technology', 'https://www.indiatoday.in/rss/1206688', 'indian', 'ai'),
    ('ThePrint Tech', 'https://theprint.in/category/tech/feed/', 'indian', 'ai'),  # live
    ('Express Computer', 'https://www.expresscomputer.in/feed/', 'indian', 'ai'),
    ('ETCIO', 'https://cio.economictimes.indiatimes.com/rss/topstories', 'indian', 'ai'),
    ('India AI (via Bing News)', 'https://www.bing.com/news/search?q=India+artificial+intelligence&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'indian', 'browser'),
    ('AI in Hindi (via Google News)', 'https://news.google.com/rss/search?q=%28%E0%A4%8F%E0%A4%86%E0%A4%88+OR+%22%E0%A4%86%E0%A4%B0%E0%A5%8D%E0%A4%9F%E0%A4%BF%E0%A4%AB%E0%A4%BF%E0%A4%B6%E0%A4%BF%E0%A4%AF%E0%A4%B2+%E0%A4%87%E0%A4%82%E0%A4%9F%E0%A5%87%E0%A4%B2%E0%A4%BF%E0%A4%9C%E0%A5%87%E0%A4%82%E0%A4%B8%22%29+when%3A1d&hl=hi&gl=IN&ceid=IN:hi', 'indian', 'top'),

    # --- world -> Global AI News (regional coverage)
    ('China AI (via Google News)', 'https://news.google.com/rss/search?q=China+(AI+OR+%22artificial+intelligence%22)+when:1d&hl=en-US&gl=US&ceid=US:en', 'world', ''),
    ('Europe AI (via Google News)', 'https://news.google.com/rss/search?q=(Europe+OR+EU+OR+%22European+Union%22)+(%22AI+Act%22+OR+AI+OR+%22artificial+intelligence%22)+when:1d&hl=en-GB&gl=GB&ceid=GB:en', 'world', ''),
    ('Japan Korea Taiwan AI (via Google News)', 'https://news.google.com/rss/search?q=(Japan+OR+Korea+OR+Taiwan)+(AI+OR+%22artificial+intelligence%22)+when:1d&hl=en-US&gl=US&ceid=US:en', 'world', ''),
    ('Middle East AI (via Google News)', 'https://news.google.com/rss/search?q=(UAE+OR+%22Saudi+Arabia%22+OR+Qatar+OR+%22Middle+East%22)+(AI+OR+%22artificial+intelligence%22)+when:1d&hl=en-US&gl=US&ceid=US:en', 'world', ''),
    ('SCMP Tech', 'https://www.scmp.com/rss/36/feed', 'world', 'ai'),
    ('Pandaily', 'https://pandaily.com/feed/', 'world', 'ai'),
    ('TechNode Global', 'https://technode.global/feed/', 'world', 'ai'),
    ('Tech in Asia', 'https://www.techinasia.com/feed', 'world', 'ai browser'),
    ('e27', 'https://e27.co/index_wp.php/feed/', 'world', 'ai'),
    ('Korea Herald Business', 'https://www.koreaherald.com/rss/kh_Business', 'world', 'ai'),
    ('Japan Times', 'https://www.japantimes.co.jp/feed/', 'world', 'ai'),
    ('The National Technology', 'https://www.thenationalnews.com/arc/outboundfeeds/rss/category/future/technology/?outputType=xml', 'world', 'ai'),
    ('Al Jazeera', 'https://www.aljazeera.com/xml/rss/all.xml', 'world', 'ai'),
    ('TechCabal', 'https://techcabal.com/feed/', 'world', 'ai'),
    ('Disrupt Africa', 'https://disruptafrica.com/feed/', 'world', 'ai'),
    ('Rest of World', 'https://restofworld.org/feed/latest', 'world', 'ai'),
    ('Politico Europe Technology', 'https://www.politico.eu/section/technology/feed/', 'world', 'ai'),  # live
    ('ChinaTalk', 'https://www.chinatalk.media/feed', 'world', ''),
    # Added 2026-10-03 ("search everywhere on the internet on Earth"): the same AI
    # search in Google News' regional editions, each led by that country's own outlets,
    # and regional outlets with their own feeds. "top" keeps each edition's first 20.
    ('UK AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-GB&gl=GB&ceid=GB:en', 'world', 'top'),
    ('Australia AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-AU&gl=AU&ceid=AU:en', 'world', 'top'),
    ('Canada AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-CA&gl=CA&ceid=CA:en', 'world', 'top'),
    ('Singapore AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-SG&gl=SG&ceid=SG:en', 'world', 'top'),
    ('South Africa AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-ZA&gl=ZA&ceid=ZA:en', 'world', 'top'),
    ('Nigeria AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-NG&gl=NG&ceid=NG:en', 'world', 'top'),
    ('Kenya AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-KE&gl=KE&ceid=KE:en', 'world', 'top'),
    ('Ireland AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-IE&gl=IE&ceid=IE:en', 'world', 'top'),
    ('New Zealand AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-NZ&gl=NZ&ceid=NZ:en', 'world', 'top'),
    ('Philippines AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-PH&gl=PH&ceid=PH:en', 'world', 'top'),
    ('Malaysia AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-MY&gl=MY&ceid=MY:en', 'world', 'top'),
    ('Pakistan AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-PK&gl=PK&ceid=PK:en', 'world', 'top'),
    ('UAE AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-AE&gl=AE&ceid=AE:en', 'world', 'top'),
    ('Israel AI (via Google News)', 'https://news.google.com/rss/search?q=%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-IL&gl=IL&ceid=IL:en', 'world', 'top'),
    ('Africa AI (via Google News)', 'https://news.google.com/rss/search?q=%28Africa+OR+Nigeria+OR+Kenya+OR+%22South+Africa%22+OR+Egypt%29+%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'world', 'top'),
    ('Latin America AI (via Google News)', 'https://news.google.com/rss/search?q=%28Brazil+OR+Mexico+OR+Argentina+OR+Chile+OR+Colombia+OR+%22Latin+America%22%29+%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'world', 'top'),
    ('Southeast Asia AI (via Google News)', 'https://news.google.com/rss/search?q=%28Singapore+OR+Indonesia+OR+Vietnam+OR+Malaysia+OR+Thailand+OR+Philippines%29+%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'world', 'top'),
    ('China AI (via Bing News)', 'https://www.bing.com/news/search?q=China+AI&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'world', 'browser'),
    ('Europe AI (via Bing News)', 'https://www.bing.com/news/search?q=Europe+AI&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'world', 'browser'),
    ('AI Policy (via Bing News)', 'https://www.bing.com/news/search?q=AI+regulation&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'world', 'browser'),
    ('Digitimes Asia', 'https://www.digitimes.com/rss/daily.xml', 'world', 'ai'),
    ('CNA Business', 'https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6936', 'world', 'ai'),
    ('Euronews Next', 'https://www.euronews.com/rss?level=vertical&name=next', 'world', 'ai'),
    ('Silicon Republic', 'https://www.siliconrepublic.com/feed', 'world', 'ai'),
    ('UKTN', 'https://www.uktech.news/feed', 'world', 'ai'),  # live
    ('Irish Times Technology', 'https://www.irishtimes.com/arc/outboundfeeds/feed-technology/?outputType=xml', 'world', 'ai'),  # live
    ('Ventureburn', 'https://ventureburn.com/feed/', 'world', 'ai'),
    ('iTnews Australia', 'https://www.itnews.com.au/RSS/rss.ashx', 'world', 'ai'),
    ('SmartCompany', 'https://www.smartcompany.com.au/feed/', 'world', 'ai'),  # live
    ('BetaKit', 'https://betakit.com/feed/', 'world', 'ai'),
    ('Globe and Mail Technology', 'https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/business/technology/', 'world', 'ai'),
    ('Wamda', 'https://www.wamda.com/feed', 'world', 'ai'),  # live
    ('European Commission Press', 'https://ec.europa.eu/commission/presscorner/api/rss?language=en', 'world', 'ai'),
    ('EU Digital Strategy', 'https://digital-strategy.ec.europa.eu/en/rss.xml', 'world', 'ai'),  # live
    ('UK Government AI news', 'https://www.gov.uk/search/news-and-communications.atom?keywords=artificial+intelligence&order=updated-newest', 'world', ''),  # live
    ('FTC Press Releases', 'https://www.ftc.gov/feeds/press-release.xml', 'world', 'ai'),  # live
    ('NIST News', 'https://www.nist.gov/news-events/news/rss.xml', 'world', 'ai'),  # live
    ('CSET Georgetown', 'https://cset.georgetown.edu/feed/', 'world', 'ai'),  # live
    ('The Hill Technology', 'https://thehill.com/policy/technology/feed/', 'world', 'ai'),
    ('Politico Technology', 'https://rss.politico.com/technology.xml', 'world', 'ai'),

    # --- world_lang -> Global AI News (added 2026-10-03): the AI search in other
    # languages, in each language's Google News edition. Read and summarised in English;
    # the builder gives each story an English title (S(..., title=...)).
    ('AI in German (via Google News)', 'https://news.google.com/rss/search?q=%28%22k%C3%BCnstliche+Intelligenz%22+OR+KI%29+when%3A1d&hl=de&gl=DE&ceid=DE:de', 'world_lang', 'top'),
    ('AI in French (via Google News)', 'https://news.google.com/rss/search?q=%22intelligence+artificielle%22+when%3A1d&hl=fr&gl=FR&ceid=FR:fr', 'world_lang', 'top'),
    ('AI in Spanish (via Google News)', 'https://news.google.com/rss/search?q=%22inteligencia+artificial%22+when%3A1d&hl=es&gl=ES&ceid=ES:es', 'world_lang', 'top'),
    ('AI in LatAm Spanish (via Google News)', 'https://news.google.com/rss/search?q=%22inteligencia+artificial%22+when%3A1d&hl=es-419&gl=MX&ceid=MX:es-419', 'world_lang', 'top'),
    ('AI in Portuguese (via Google News)', 'https://news.google.com/rss/search?q=%22intelig%C3%AAncia+artificial%22+when%3A1d&hl=pt-BR&gl=BR&ceid=BR:pt-419', 'world_lang', 'top'),
    ('AI in Italian (via Google News)', 'https://news.google.com/rss/search?q=%22intelligenza+artificiale%22+when%3A1d&hl=it&gl=IT&ceid=IT:it', 'world_lang', 'top'),
    ('AI in Dutch (via Google News)', 'https://news.google.com/rss/search?q=%28%22kunstmatige+intelligentie%22+OR+AI%29+when%3A1d&hl=nl&gl=NL&ceid=NL:nl', 'world_lang', 'top'),
    ('AI in Polish (via Google News)', 'https://news.google.com/rss/search?q=%22sztuczna+inteligencja%22+when%3A1d&hl=pl&gl=PL&ceid=PL:pl', 'world_lang', 'top'),
    ('AI in Turkish (via Google News)', 'https://news.google.com/rss/search?q=%22yapay+zeka%22+when%3A1d&hl=tr&gl=TR&ceid=TR:tr', 'world_lang', 'top'),
    ('AI in Russian (via Google News)', 'https://news.google.com/rss/search?q=%22%D0%B8%D1%81%D0%BA%D1%83%D1%81%D1%81%D1%82%D0%B2%D0%B5%D0%BD%D0%BD%D1%8B%D0%B9+%D0%B8%D0%BD%D1%82%D0%B5%D0%BB%D0%BB%D0%B5%D0%BA%D1%82%22+when%3A1d&hl=ru&gl=RU&ceid=RU:ru', 'world_lang', 'top'),
    ('AI in Arabic (via Google News)', 'https://news.google.com/rss/search?q=%22%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1+%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A%22+when%3A1d&hl=ar&gl=SA&ceid=SA:ar', 'world_lang', 'top'),
    ('AI in Japanese (via Google News)', 'https://news.google.com/rss/search?q=%28%E4%BA%BA%E5%B7%A5%E7%9F%A5%E8%83%BD+OR+%E7%94%9F%E6%88%90AI%29+when%3A1d&hl=ja&gl=JP&ceid=JP:ja', 'world_lang', 'top'),
    ('AI in Korean (via Google News)', 'https://news.google.com/rss/search?q=%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5+when%3A1d&hl=ko&gl=KR&ceid=KR:ko', 'world_lang', 'top'),
    ('AI in Chinese TW (via Google News)', 'https://news.google.com/rss/search?q=%E4%BA%BA%E5%B7%A5%E6%99%BA%E6%85%A7+when%3A1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant', 'world_lang', 'top'),
    ('AI in Chinese HK (via Google News)', 'https://news.google.com/rss/search?q=%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD+when%3A1d&hl=zh-HK&gl=HK&ceid=HK:zh-Hant', 'world_lang', 'top'),
    ('AI in Indonesian (via Google News)', 'https://news.google.com/rss/search?q=%22kecerdasan+buatan%22+when%3A1d&hl=id&gl=ID&ceid=ID:id', 'world_lang', 'top'),
    ('AI in Vietnamese (via Google News)', 'https://news.google.com/rss/search?q=%22tr%C3%AD+tu%E1%BB%87+nh%C3%A2n+t%E1%BA%A1o%22+when%3A1d&hl=vi&gl=VN&ceid=VN:vi', 'world_lang', 'top'),
    ('ITmedia AI+', 'https://rss.itmedia.co.jp/rss/2.0/aiplus.xml', 'world_lang', ''),  # Japanese

    # --- general -> Global AI News, and leads for every section
    ('The Verge AI', 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml', 'general', ''),
    ('TechCrunch AI', 'https://techcrunch.com/category/artificial-intelligence/feed/', 'general', ''),
    ('Ars Technica AI', 'https://feeds.arstechnica.com/arstechnica/technology-lab', 'general', 'ai'),
    ('MIT Technology Review', 'https://www.technologyreview.com/feed/', 'general', 'ai'),
    ('VentureBeat AI', 'https://venturebeat.com/category/ai/feed/', 'general', ''),
    ('The Decoder', 'https://the-decoder.com/feed/', 'general', ''),
    ('AI News', 'https://www.artificialintelligence-news.com/feed/', 'general', ''),
    ('Wired AI', 'https://www.wired.com/feed/tag/ai/latest/rss', 'general', ''),
    ('The Register AI', 'https://www.theregister.com/software/ai_ml/headlines.atom', 'general', ''),
    ('Futurism', 'https://futurism.com/feed', 'general', 'ai'),
    ('Techmeme', 'https://www.techmeme.com/feed.xml', 'general', 'ai'),
    ('Bloomberg Technology', 'https://feeds.bloomberg.com/technology/news.rss', 'general', 'ai'),
    ('The Guardian AI', 'https://www.theguardian.com/technology/artificialintelligenceai/rss', 'general', ''),
    ('BBC Technology', 'https://feeds.bbci.co.uk/news/technology/rss.xml', 'general', 'ai'),
    ('NYT Technology', 'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml', 'general', 'ai'),
    ('CNBC Technology', 'https://www.cnbc.com/id/19854910/device/rss/rss.html', 'general', 'ai'),
    ('FT Artificial Intelligence', 'https://www.ft.com/artificial-intelligence?format=rss', 'general', ''),
    ('Axios', 'https://api.axios.com/feed/', 'general', 'ai'),
    ('Engadget', 'https://www.engadget.com/rss.xml', 'general', 'ai'),
    ('Gizmodo AI', 'https://gizmodo.com/tag/artificial-intelligence/rss', 'general', ''),
    ('The Next Web', 'https://thenextweb.com/feed', 'general', 'ai'),
    ('Fast Company Tech', 'https://www.fastcompany.com/technology/rss', 'general', 'ai'),
    ('Fortune', 'https://fortune.com/feed/fortune-feeds/?id=3230629', 'general', 'ai'),
    ('Business Insider', 'https://feeds.businessinsider.com/custom/all', 'general', 'ai'),
    ('Semafor', 'https://www.semafor.com/rss.xml', 'general', 'ai'),
    ('MarkTechPost', 'https://www.marktechpost.com/feed/', 'general', ''),
    ('SiliconANGLE AI', 'https://siliconangle.com/category/ai/feed/', 'general', ''),
    ("Tom's Hardware", 'https://www.tomshardware.com/feeds/all', 'general', 'ai'),
    ('Unite.AI', 'https://www.unite.ai/feed/', 'general', ''),
    ('TechRepublic AI', 'https://www.techrepublic.com/rssfeeds/topic/artificial-intelligence/', 'general', ''),  # live
    ('IEEE Spectrum AI', 'https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss', 'general', ''),  # live
    ('Latent Space', 'https://www.latent.space/feed', 'general', ''),
    ('TLDR AI', 'https://tldr.tech/api/rss/ai', 'general', ''),
    ('The Rundown AI', 'https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml', 'general', ''),
    ('Simon Willison', 'https://simonwillison.net/atom/everything/', 'general', ''),  # live
    ('Import AI', 'https://importai.substack.com/feed', 'general', ''),  # live
    ('Last Week in AI', 'https://lastweekin.ai/feed', 'general', ''),  # live
    ("Ben's Bites", 'https://www.bensbites.com/feed', 'general', ''),  # live
    ('One Useful Thing', 'https://www.oneusefulthing.org/feed', 'general', ''),  # live
    ('Platformer', 'https://www.platformer.news/rss/', 'general', 'ai'),  # live
    ('Big Technology', 'https://www.bigtechnology.com/feed', 'general', 'ai'),  # live
    ('Stratechery', 'https://stratechery.com/feed/', 'general', 'ai'),  # live
    ('Exponential View', 'https://www.exponentialview.co/feed', 'general', 'ai'),  # live
    ('AI Supremacy', 'https://www.ai-supremacy.com/feed', 'general', ''),  # live
    ('The Algorithmic Bridge', 'https://www.thealgorithmicbridge.com/feed', 'general', ''),  # live
    ('Interconnects', 'https://www.interconnects.ai/feed', 'general', ''),  # live
    ('Ahead of AI', 'https://magazine.sebastianraschka.com/feed', 'general', ''),  # live
    ('Understanding AI', 'https://www.understandingai.org/feed', 'general', ''),  # live
    # Added 2026-10-03: wire services and papers through Google News (their own pages
    # block fetching, so fetch_articles.py reads the story from another outlet; the
    # site: searches match far beyond AI, 4-20 in 100 on the first run, hence "ai"), and
    # more mainstream, consumer-tech and newsletter outlets.
    ('AI news (Google News topic)', 'https://news.google.com/rss/topics/CAAqIAgKIhpDQkFTRFFvSEwyMHZNRzFyZWhJQ1pXNG9BQVAB?hl=en-US&gl=US&ceid=US:en', 'general', ''),
    ('Reuters AI (via Google News)', 'https://news.google.com/rss/search?q=site%3Areuters.com+%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'general', 'ai'),
    ('AP AI (via Google News)', 'https://news.google.com/rss/search?q=site%3Aapnews.com+%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'general', 'ai'),
    ('WSJ AI (via Google News)', 'https://news.google.com/rss/search?q=site%3Awsj.com+%28AI+OR+%22artificial+intelligence%22%29+when%3A1d&hl=en-US&gl=US&ceid=US:en', 'general', 'ai'),
    ('Washington Post Technology', 'https://feeds.washingtonpost.com/rss/business/technology', 'general', 'ai'),
    ('CBS News Technology', 'https://www.cbsnews.com/latest/rss/technology', 'general', 'ai'),
    ('ABC News Technology', 'https://abcnews.go.com/abcnews/technologyheadlines', 'general', 'ai'),  # live
    ('The Atlantic Technology', 'https://www.theatlantic.com/feed/channel/technology/', 'general', 'ai'),  # live
    ('Vox Technology', 'https://www.vox.com/rss/technology/index.xml', 'general', 'ai'),
    ('Time Tech', 'https://time.com/tech/feed/', 'general', 'ai'),
    ('LA Times Business', 'https://www.latimes.com/business/rss2.0.xml', 'general', 'ai'),
    ('The Independent Tech', 'https://www.independent.co.uk/tech/rss', 'general', 'ai'),
    ('Sky News Technology', 'https://feeds.skynews.com/feeds/rss/technology.xml', 'general', 'ai'),  # live
    ('The Economist Science and Technology', 'https://www.economist.com/science-and-technology/rss.xml', 'general', 'ai'),  # live
    ('The Information', 'https://www.theinformation.com/feed', 'general', 'ai'),
    ('Forbes Innovation', 'https://www.forbes.com/innovation/feed/', 'general', 'ai'),
    ('CNET AI', 'https://www.cnet.com/rss/ai/', 'general', ''),
    ('ZDNET', 'https://www.zdnet.com/news/rss.xml', 'general', 'ai'),
    ('PCMag', 'https://www.pcmag.com/feeds/rss/latest', 'general', 'ai'),
    ('PCWorld', 'https://www.pcworld.com/feed', 'general', 'ai'),
    ('Mashable Tech', 'https://mashable.com/feeds/rss/tech', 'general', 'ai'),
    ('9to5Mac', 'https://9to5mac.com/feed/', 'general', 'ai'),
    ('MacRumors', 'https://feeds.macrumors.com/MacRumors-All', 'general', 'ai'),
    ('Android Authority', 'https://www.androidauthority.com/feed/', 'general', 'ai'),
    ('Android Police', 'https://www.androidpolice.com/feed/', 'general', 'ai'),
    ('XDA', 'https://www.xda-developers.com/feed/', 'general', 'ai'),
    ('Data Center Dynamics', 'https://www.datacenterdynamics.com/en/rss/', 'general', 'ai'),
    ('EE Times', 'https://www.eetimes.com/feed/', 'general', 'ai'),
    ('Daring Fireball', 'https://daringfireball.net/feeds/main', 'general', 'ai'),
    ('Marginal Revolution', 'https://marginalrevolution.com/feed', 'general', 'ai'),
    ('Gradient Flow', 'https://gradientflow.substack.com/feed', 'general', ''),  # live
    ('Artificial Ignorance', 'https://www.ignorance.ai/feed', 'general', ''),  # live
    ('Air Street Press', 'https://press.airstreet.com/feed', 'general', ''),  # live

    # --- company_blog -> Global AI News (AI companies other than the four with their own section)
    ('NVIDIA Blog', 'https://blogs.nvidia.com/feed/', 'company_blog', 'ai'),
    ('NVIDIA Developer Blog', 'https://developer.nvidia.com/blog/feed', 'company_blog', 'ai'),
    ('Microsoft Blog', 'https://blogs.microsoft.com/feed/', 'company_blog', 'ai'),  # live
    ('Meta Newsroom', 'https://about.fb.com/news/feed/', 'company_blog', 'ai'),  # live
    ('Meta Engineering', 'https://engineering.fb.com/feed/', 'company_blog', 'ai'),  # live
    ('Microsoft Source', 'https://news.microsoft.com/source/feed/', 'company_blog', 'ai'),
    ('Azure Blog', 'https://azure.microsoft.com/en-us/blog/feed/', 'company_blog', 'ai'),  # live
    ('Amazon News', 'https://www.aboutamazon.com/news/rss', 'company_blog', 'ai'),
    ('Apple Newsroom', 'https://www.apple.com/newsroom/rss-feed.rss', 'company_blog', 'ai'),  # live
    ('Samsung Newsroom', 'https://news.samsung.com/global/feed', 'company_blog', 'ai'),
    ('Together AI Blog', 'https://www.together.ai/blog/rss.xml', 'company_blog', ''),  # live

    # --- openai -> OpenAI (the existing "OpenAI Blog" feed moves here)
    ('OpenAI Blog', 'https://openai.com/blog/rss.xml', 'openai', ''),
    ('OpenAI (via Google News)', 'https://news.google.com/rss/search?q=OpenAI+OR+ChatGPT+OR+%22Sam+Altman%22+when:1d&hl=en-US&gl=US&ceid=US:en', 'openai', ''),  # new-query
    ('OpenAI (via Bing News)', 'https://www.bing.com/news/search?q=OpenAI&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'openai', 'browser'),
    ('Sam Altman on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fsama&hl=en-US&gl=US&ceid=US:en', 'openai', ''),
    ('OpenAI on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2FOpenAI&hl=en-US&gl=US&ceid=US:en', 'openai', ''),  # live
    ('OpenAI Developers on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2FOpenAIDevs&hl=en-US&gl=US&ceid=US:en', 'openai', ''),
    ('OpenAI YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCXZCJLdBC09xxGZ6gcdrc6A', 'openai', ''),

    # --- google -> Google AI (the existing "Google AI Blog" feed moves here)
    ('Google AI Blog', 'https://blog.google/technology/ai/rss/', 'google', ''),
    ('Google DeepMind Blog', 'https://deepmind.google/blog/rss.xml', 'google', ''),  # live
    ('Google Research Blog', 'https://research.google/blog/rss/', 'google', ''),
    ('Gemini Blog', 'https://blog.google/products/gemini/rss/', 'google', ''),
    ('Google Cloud AI Blog', 'https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/', 'google', ''),  # live
    ('Google AI (via Google News)', 'https://news.google.com/rss/search?q=(Gemini+OR+DeepMind+OR+%22Google+AI%22)+(Google+OR+AI)+when:1d&hl=en-US&gl=US&ceid=US:en', 'google', ''),  # new-query
    ('Google AI (via Bing News)', 'https://www.bing.com/news/search?q=Google+Gemini+AI&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'google', 'browser'),  # new-query
    ('Google DeepMind on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2FGoogleDeepMind&hl=en-US&gl=US&ceid=US:en', 'google', ''),
    ('Google AI on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2FGoogleAI&hl=en-US&gl=US&ceid=US:en', 'google', ''),  # live
    ('Sundar Pichai on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fsundarpichai&hl=en-US&gl=US&ceid=US:en', 'google', ''),
    ('Demis Hassabis on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fdemishassabis&hl=en-US&gl=US&ceid=US:en', 'google', ''),  # live
    ('Google DeepMind YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCP7jMXSY2xbc3KCAE0MHQ-A', 'google', ''),
    ('Google YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCK8sQmJBp8GCxrOtXWBpyEA', 'google', 'ai'),  # live
    ('9to5Google', 'https://9to5google.com/feed/', 'google', 'ai'),

    # --- anthropic_claude -> Anthropic & Claude Code (the two existing Google News searches stay)
    # anthropic.com/rss.xml returns 404 - proxy via Google News (same trick as the
    # Musk feed below). Two queries: company/model news, and Claude Code specifically.
    ('Anthropic News (via Google News)', 'https://news.google.com/rss/search?q=Anthropic+OR+%22Claude+Opus%22+OR+%22Claude+Sonnet%22+when:2d&hl=en-US&gl=US&ceid=US:en', 'anthropic_claude', ''),
    ('Claude Code (via Google News)', 'https://news.google.com/rss/search?q=%22Claude+Code%22+OR+%22Claude+Agent+SDK%22+OR+%22Claude+Skills%22+when:3d&hl=en-US&gl=US&ceid=US:en', 'anthropic_claude', ''),
    ('Anthropic (via Bing News)', 'https://www.bing.com/news/search?q=Anthropic+Claude&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'anthropic_claude', 'browser'),  # new-query
    ('Anthropic on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2FAnthropicAI&hl=en-US&gl=US&ceid=US:en', 'anthropic_claude', ''),
    ('Claude on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fclaudeai&hl=en-US&gl=US&ceid=US:en', 'anthropic_claude', ''),
    ('Dario Amodei on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2FDarioAmodei&hl=en-US&gl=US&ceid=US:en', 'anthropic_claude', ''),  # live
    ('Anthropic YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCrDwWp7EBBv4NwvScIpBDOA', 'anthropic_claude', ''),  # live
    ('Claude Code Releases', 'https://github.com/anthropics/claude-code/releases.atom', 'anthropic_claude', ''),

    # --- xai_grok -> xAI & Grok (x.ai has no feed; the company now brands itself SpaceXAI on its own pages)
    ('xAI & Grok (via Google News)', 'https://news.google.com/rss/search?q=xAI+OR+Grok+OR+SpaceXAI+when:1d&hl=en-US&gl=US&ceid=US:en', 'xai_grok', ''),  # new-query
    ('xAI & Grok (via Bing News)', 'https://www.bing.com/news/search?q=xAI+Grok&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'xai_grok', 'browser'),  # new-query
    ('xAI official site (via Google News)', 'https://news.google.com/rss/search?q=site:x.ai&hl=en-US&gl=US&ceid=US:en', 'xai_grok', ''),  # new-query
    ('Tesla YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCr7nsg_hE_t06057x51g_Fg', 'xai_grok', 'ai'),

    # --- open_model -> Open Models & Open Weights (the five existing feeds stay)
    # Open-weight releases usually break on Hugging Face, Reddit and vendor blogs
    # a day or two before the general AI outlets pick them up, so this section gets
    # its own sources rather than living off the general feeds.
    ('Hugging Face Blog', 'https://huggingface.co/blog/feed.xml', 'open_model', ''),
    ('Open Models (via Google News)', 'https://news.google.com/rss/search?q=(%22open+weights%22+OR+%22open-weight+model%22+OR+%22open+source+model%22)+(Llama+OR+Qwen+OR+DeepSeek+OR+Mistral+OR+Gemma+OR+Kimi+OR+GLM+OR+OLMo+OR+Falcon)+when:2d&hl=en-US&gl=US&ceid=US:en', 'open_model', ''),
    ('Open Model Benchmarks (via Google News)', 'https://news.google.com/rss/search?q=(%22open+model%22+OR+%22open-weight%22+OR+%22open+source+LLM%22)+(benchmark+OR+leaderboard+OR+outperforms+OR+release)+when:3d&hl=en-US&gl=US&ceid=US:en', 'open_model', ''),
    # Highest-yield open-model source by a wide margin (20 of 25 entries inside 24h
    # when probed). Community posts, so weight the *linked* release over the commentary.
    # Reddit ends this RSS feed on 13 Nov 2026; "Hugging Face new models" in EXTRA
    # is the replacement already in place.
    ('r/LocalLLaMA', 'https://www.reddit.com/r/LocalLLaMA/.rss', 'open_model', ''),
    # Live but infrequent (roughly fortnightly) - carries local-model release notes.
    ('Ollama Blog', 'https://ollama.com/blog/rss.xml', 'open_model', ''),
    ('Mistral AI News', 'https://mistral.ai/rss.xml', 'open_model', ''),  # live
    ('Open Models (via Bing News)', 'https://www.bing.com/news/search?q=open+source+AI+model&qft=interval%3d%227%22+sortbydate%3d%221%22&form=PTFTNR&format=rss', 'open_model', 'browser'),

    # --- closed_model -> Closed Models & Frontier APIs
    ('Closed Models (via Google News)', 'https://news.google.com/rss/search?q=(GPT+OR+Gemini+OR+%22Claude+Opus%22+OR+Grok)+(benchmark+OR+pricing+OR+leaderboard+OR+%22new+model%22)+when:1d&hl=en-US&gl=US&ceid=US:en', 'closed_model', ''),

    # --- elon_musk -> Elon Musk on AI (his own point of view; the existing "Elon Musk on X" search stays)
    # Elon Musk posts on x.com - direct scraping requires auth (402), so we
    # proxy via Google News RSS filtered to site:x.com/elonmusk
    ('Elon Musk on X (via Google News)', 'https://news.google.com/rss/search?q=%22elon+musk%22+(xAI+OR+Grok+OR+AI)+site:x.com%2Felonmusk&hl=en-US&gl=US&ceid=US:en', 'elon_musk', ''),
    ('Elon Musk all posts on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Felonmusk&hl=en-US&gl=US&ceid=US:en', 'elon_musk', 'ai'),
    ('Elon Musk on AI (via Google News)', 'https://news.google.com/rss/search?q=%22Elon+Musk%22+(AI+OR+xAI+OR+Grok+OR+AGI+OR+superintelligence+OR+Optimus+OR+robotaxi)+when:1d&hl=en-US&gl=US&ceid=US:en', 'elon_musk', ''),  # new-query
    ('Elon Musk on AI (via Bing News)', 'https://www.bing.com/news/search?q=%22Elon+Musk%22+AI&qft=interval%3d%227%22&format=rss', 'elon_musk', 'browser'),
    ('Teslarati', 'https://www.teslarati.com/feed/', 'elon_musk', 'musk'),
    ('Electrek', 'https://electrek.co/feed/', 'elon_musk', 'musk'),

    # --- video -> leads for any section (YouTube channel feeds; no API key)
    ('AI Explained YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCNJ1Ymd5yFuUPtn21xtRbbw', 'video', ''),
    ('Matthew Berman YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCawZsQWqfGSbCI5yjkdVkTA', 'video', ''),
    ('Wes Roth YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCqcbQf6yw5KzRoDDcZ_wBSw', 'video', ''),  # live
    ('Two Minute Papers YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg', 'video', ''),  # live
    ('Matt Wolfe YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UChpleBmo18P08aKCIgti38g', 'video', ''),
    ('AI Engineer YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCLKPca3kwwd-B59HNr-_lvA', 'video', ''),
    ('Latent Space Podcast YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCxBcwypKK-W3GHd_RZ9FZrQ', 'video', ''),
    ('Greg Isenberg YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCPjNBjflYl0-HQtUvOx0Ibw', 'video', ''),
    ('Dwarkesh Patel YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCZa18YV7qayTh-MRIrBhDpA', 'video', 'ai'),
    ('Lex Fridman YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCJIfeSCssxSC_Dhc5s7woww', 'video', 'ai'),  # live
    ('Y Combinator YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCxIJaCMEptJjxmmQgGFsnCg', 'video', 'ai'),
    ('All-In Podcast YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCESLZhusAkFfsNsApnjF_Cg', 'video', 'ai'),
    ('NVIDIA YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCL-g3eGJi1omSDSz48AML-g', 'video', 'ai'),
    # Added 2026-10-03: more channels, and podcasts (their show notes name the stories).
    ('AI Daily Brief YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCKelCK4ZaO6HeEI1KQjqzWA', 'video', ''),
    ('bycloud YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCgfe2ooZD3VJPB6aJAnuQng', 'video', ''),
    ('Sam Witteveen YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UC55ODQSvARtgSyc8ThfiepQ', 'video', ''),
    ('IBM Technology YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCKWaEZ-_VweaEx1j62do_vQ', 'video', ''),
    ('Fireship YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCsBjURrPoezykLs9EqgamOA', 'video', 'ai'),
    ('Theo YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCbRP3c757lWg9M-U7TyEkXA', 'video', 'ai'),
    ('Hugging Face YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCHlNU7kIZhRgSbhHvFoy72w', 'video', ''),  # live
    ('Microsoft Research YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCCb9_Kn8F_Opb3UCGm-lILQ', 'video', 'ai'),  # live
    ('Andrej Karpathy YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCXUPKJO5MZQN11PqgIvyuvQ', 'video', ''),  # live
    ('Bloomberg Technology YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCrM7B7SL_g1edFOnmj-SDKg', 'video', 'ai'),
    ('CNBC Television YouTube', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCrp_UI8XtuYfpiqluWLD7Lw', 'video', 'ai'),
    ('AI Daily Brief podcast', 'https://anchor.fm/s/f7cac464/podcast/rss', 'video', ''),
    ('Hard Fork podcast', 'https://feeds.simplecast.com/l2i9YnTd', 'video', 'ai'),  # live
    ('No Priors podcast', 'https://feeds.megaphone.fm/nopriors', 'video', ''),  # live
    ('Decoder podcast', 'https://feeds.megaphone.fm/recodedecode', 'video', 'ai'),  # live
    ('Practical AI podcast', 'https://changelog.com/practicalai/feed', 'video', ''),  # live
    ('TWIML AI podcast', 'https://feeds.megaphone.fm/MLN2155636147', 'video', ''),  # live

    # --- social -> leads for any section
    ('Andrej Karpathy on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fkarpathy&hl=en-US&gl=US&ceid=US:en', 'social', ''),
    ('Yann LeCun on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fylecun&hl=en-US&gl=US&ceid=US:en', 'social', ''),  # live
    ('Satya Nadella on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fsatyanadella&hl=en-US&gl=US&ceid=US:en', 'social', ''),  # live
    ('NVIDIA on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fnvidia&hl=en-US&gl=US&ceid=US:en', 'social', ''),
    ('Slashdot', 'https://rss.slashdot.org/Slashdot/slashdotMain', 'social', 'ai'),
    ('Lobsters AI', 'https://lobste.rs/t/ai.rss', 'social', ''),  # live

    # --- forums -> leads for any section (added 2026-10-03). Community posts: weight the
    # release or article a post links to over the post. Reddit ends RSS on 13 Nov 2026,
    # so the four Reddit rows go dark then; Bluesky profile feeds carry no titles, so the
    # scraper titles each post with its opening words.
    ('r/singularity', 'https://www.reddit.com/r/singularity/.rss', 'forums', ''),
    ('r/OpenAI', 'https://www.reddit.com/r/OpenAI/.rss', 'forums', ''),
    ('r/ClaudeAI', 'https://www.reddit.com/r/ClaudeAI/.rss', 'forums', ''),
    ('r/artificial', 'https://www.reddit.com/r/artificial/.rss', 'forums', ''),
    ('r/MachineLearning', 'https://www.reddit.com/r/MachineLearning/.rss', 'forums', 'browser'),
    ('Ethan Mollick on Bluesky', 'https://bsky.app/profile/emollick.bsky.social/rss', 'forums', 'ai'),
    ('Nathan Lambert on Bluesky', 'https://bsky.app/profile/natolambert.bsky.social/rss', 'forums', 'ai'),
    ('Casey Newton on Bluesky', 'https://bsky.app/profile/caseynewton.bsky.social/rss', 'forums', 'ai'),
    ('Emily Bender on Bluesky', 'https://bsky.app/profile/emilymbender.bsky.social/rss', 'forums', 'ai'),
    ('Melanie Mitchell on Bluesky', 'https://bsky.app/profile/melaniemitchell.bsky.social/rss', 'forums', 'ai'),  # live
    ('David Ha on Bluesky', 'https://bsky.app/profile/hardmaru.bsky.social/rss', 'forums', 'ai'),  # live
    ('Margaret Mitchell on Bluesky', 'https://bsky.app/profile/mmitchell.bsky.social/rss', 'forums', 'ai'),  # live
]

# The non-RSS readers. Each reader takes (name, arg, cutoff_time) and returns the
# same article dicts as a feed; parsing lives in pure functions so tests run offline.
EXTRA = [
    ("Hacker News", "social", "hn", ""),
    ("Hugging Face new models", "open_model", "hf_models", ""),
    ("YouTube search: Elon Musk AI", "elon_musk", "yt_search", "Elon Musk AI"),
    ("YouTube search: AI news", "video", "yt_search", "AI news"),
]

# ── Rejected: tested and not worth retrying ──────────────────────────────────
# Removed 2026-10-02: ZDNet AI (topic RSS 404) and xAI Blog (x.ai/blog/rss.xml 404),
# both dead for weeks.
#
# Hackathon platforms (probed 2026-09-07 and 2026-10-02):
#   devpost.com/hackathons.rss -> 406 on a bot UA and a browser UA (the Devpost
#     JSON API in find_opportunities.py is used instead)
#   mlh.io/seasons/2026/events.rss -> 200 but zero entries; MLH and HackClub are
#     students only, which the curator profile excludes
#   hackerearth.com/challenges/feed/ -> 404, and the site is client-rendered
#   indiaai.gov.in/rss and /feed -> 404
#   opportunitydesk.org/feed/ -> live, but general opportunities (water prizes,
#     film fellowships); the AI hit rate was too low to justify the noise
#   DoraHacks API 404, Kaggle reCAPTCHA, AIcrowd 500, challenge.gov API 404,
#     hackathons.io timeout. Load but have no parser yet, lower priority: TAIKAI,
#     lu.ma/ai, Cerebral Valley, Eventbrite, hackathon.com.
#
# X, direct: the syndication timeline endpoint answers 429; Nitter mirrors are down
#   or blocked (xcancel 451; nitter.net, poast, privacydev unreachable; tiekoetter
#   captcha; nitter.space and lightbrd 403); RSSHub routes 404. site:x.com/xai has 3
#   posts, the newest from May 2026; site:x.com/grok is Grok's automatic replies, so
#   neither @grok nor @xai is added. YouTube @xai has one video from 2022.
#   x.ai/news/rss.xml and x.ai/blog/rss.xml are 404.
#
# News feeds dead, blocked or stale: Forbes AI (404), Stanford HAI and The Neuron
#   (no entries), WSJ Technology (newest Jan 2026), Synced (Aug 2026), The Gradient
#   (Feb 2026), BAIR (Jul 2026), OpenAI Alignment blog (Jul 2026), Hyperdimensional
#   (1 Sep 2026), blogs.microsoft.com/ai/feed (410), Google Developers Blog (entries
#   carry no date, so every one is dropped), Epoch AI atom (404), AI Frontiers (404),
#   Anthropic Alignment blog (404), Apollo Research and LangChain (no entries),
#   LlamaIndex (404), Make (403), HBR (SSL error), EU-Startups, Tech Funding News,
#   FinSMEs and Euractiv (403), TechNode's main feed (2,000 entries; TechNode Global
#   is used), Nikkei Asia, KED Global and PIB (undated), dev.to and Medium AI tags
#   (noise).
#
# India: Analytics India Magazine, ET AI, Financial Express and CXOToday (no
#   entries), Gadgets360 and NDTV Profit (403), VCCircle (500), Times of India Tech
#   (newest Aug 2026), Moneycontrol (Apr 2026).
#
# Probed 2026-10-03 and rejected (the "search everywhere" pass; ~300 candidates):
#   403/402/451 to bot and browser: NPR, USA Today, Telegraph, BigDATAwire, HPCwire,
#     News18, Firstpost, Gadgets360, Euractiv, Techpoint Africa, MyBroadband,
#     InnovationAus, Times of Israel, Gulf Business, Lawfare, Perplexity, AMD, Intel,
#     Bangkok Post, and every github.com releases.atom feed (ollama, vllm,
#     transformers, llama.cpp, gemini-cli, codex, claude-code, langchain).
#   404: Newsweek, KrASIA, Taipei Times, Focus Taiwan, JoongAng Daily, Yonhap,
#     Caixin, China Daily, Deccan Herald, France 24, CTech, Gulf News, Khaleej Times,
#     Techeconomy, UK AISI, White House, OECD.AI, Center for AI Policy, Allen AI,
#     EleutherAI, IBM Research, ElevenLabs, Modal, Pinecone, Meta AI blog, Qualcomm,
#     Mistral changelog, anthropic.com news/engineering, claude.com blog, Turing
#     Post, Superhuman AI, The Batch, Cognitive Revolution, TechTarget AI.
#   No entries or undated: 36Kr, Nikkei Asia (undated), Sixth Tone (undated),
#     Scroll, Financial Express, Analytics India Magazine, DW, LABS, Arab News,
#     Tech Policy Press, Brookings, IAPP, Cohere, Stability AI, IBM Think, Baidu
#     Research, DeepSeek news, Every, The Neuron, Google Developers Blog (undated).
#   Stale: CNN tech (2025), Yahoo Finance, Global Times, Times of India Tech,
#     Moneycontrol, Scientific American, Knowable, Replicate, W&B, Microsoft AI blog,
#     Nathan Benaich, Davis Summarizes Papers, Om Malik, Benedict Evans, Hyperdimensional,
#     Qwen blog (still 2025-09-22), Yannic Kilcher, Krebs.
#   Noise or off-topic for the AI filter: Hacker Noon, Analytics Insight, Pakistan
#     Dawn, Nautilus, heise and t3n (German "KI" escapes the English AI filter; the
#     German Google News search covers them), Le Monde and El Pais (same reason),
#     Mastodon hashtag feeds (random posts by anyone, newest first).
#   Bluesky's search API answers 403 without a login; its profile RSS works.
#
# Search and social: Yahoo News RSS (empty or 404), DuckDuckGo HTML (no dates),
#   Bluesky profile RSS (empty or 404 for some handles; working ones are in
#   forums above), Reddit multi-subreddit URLs (429;
#   r/LocalLLaMA alone works until 13 Nov 2026), hnrss.org (502 at times; the
#   Algolia API in EXTRA is used), Hugging Face daily papers (days behind; arXiv
#   covers them).
#
# Open-model feeds (probed 2026-09-07): mistral.ai/news/feed.xml,
#   ai.meta.com/blog/rss/, lmstudio.ai/blog/rss.xml -> 404; qwenlm.github.io ->
#   200 but abandoned (newest post 2025-09-22); papers.takara.ai/api/feed -> 200 but
#   lags ~4 days. https://mistral.ai/rss.xml does work and is listed above.
