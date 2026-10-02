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

    # --- business -> AI Business Opportunities
    ('AI Funding (via Google News)', 'https://news.google.com/rss/search?q=AI+startup+(raises+OR+funding+OR+valuation+OR+%22Series+A%22+OR+%22seed+round%22)+when:1d&hl=en-US&gl=US&ceid=US:en', 'business', ''),
    ('Crunchbase News', 'https://news.crunchbase.com/feed/', 'business', 'ai'),
    ('TechCrunch Startups', 'https://techcrunch.com/category/startups/feed/', 'business', 'ai'),
    ('TechCrunch Venture', 'https://techcrunch.com/category/venture/feed/', 'business', 'ai'),
    ('AlleyWatch', 'https://www.alleywatch.com/feed/', 'business', 'ai'),
    ('Sifted', 'https://sifted.eu/feed', 'business', 'ai'),
    ('Tech.eu', 'https://tech.eu/feed/', 'business', 'ai'),

    # --- showcase -> AI Business Opportunities
    ('Product Hunt AI', 'https://www.producthunt.com/feed?category=artificial-intelligence', 'showcase', ''),

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

    # --- company_blog -> Global AI News (AI companies other than the four with their own section)
    ('NVIDIA Blog', 'https://blogs.nvidia.com/feed/', 'company_blog', 'ai'),
    ('NVIDIA Developer Blog', 'https://developer.nvidia.com/blog/feed', 'company_blog', 'ai'),
    ('Microsoft Blog', 'https://blogs.microsoft.com/feed/', 'company_blog', 'ai'),  # live
    ('Meta Newsroom', 'https://about.fb.com/news/feed/', 'company_blog', 'ai'),  # live
    ('Meta Engineering', 'https://engineering.fb.com/feed/', 'company_blog', 'ai'),  # live

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

    # --- social -> leads for any section
    ('Andrej Karpathy on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fkarpathy&hl=en-US&gl=US&ceid=US:en', 'social', ''),
    ('Yann LeCun on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fylecun&hl=en-US&gl=US&ceid=US:en', 'social', ''),  # live
    ('Satya Nadella on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fsatyanadella&hl=en-US&gl=US&ceid=US:en', 'social', ''),  # live
    ('NVIDIA on X (via Google News)', 'https://news.google.com/rss/search?q=site:x.com%2Fnvidia&hl=en-US&gl=US&ceid=US:en', 'social', ''),
    ('Slashdot', 'https://rss.slashdot.org/Slashdot/slashdotMain', 'social', 'ai'),
    ('Lobsters AI', 'https://lobste.rs/t/ai.rss', 'social', ''),  # live
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
# Search and social: Yahoo News RSS (empty or 404), DuckDuckGo HTML (no dates),
#   Bluesky profile RSS (empty or 404), Reddit multi-subreddit URLs (429;
#   r/LocalLLaMA alone works until 13 Nov 2026), hnrss.org (502 at times; the
#   Algolia API in EXTRA is used), Hugging Face daily papers (days behind; arXiv
#   covers them).
#
# Open-model feeds (probed 2026-09-07): mistral.ai/news/feed.xml,
#   ai.meta.com/blog/rss/, lmstudio.ai/blog/rss.xml -> 404; qwenlm.github.io ->
#   200 but abandoned (newest post 2025-09-22); papers.takara.ai/api/feed -> 200 but
#   lags ~4 days. https://mistral.ai/rss.xml does work and is listed above.
