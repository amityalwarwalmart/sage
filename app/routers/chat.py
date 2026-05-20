"""Mocked chat — returns canned Sage responses based on keyword match.
Plain-English, no slash commands or technical terms.
"""
import html
from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse

router = APIRouter()


def _user_bubble(text: str) -> str:
    return f'''
    <div class="flex gap-2 justify-end">
      <div class="bg-wmblue-100 text-white rounded-2xl rounded-tr-md px-3.5 py-2.5 max-w-[85%] leading-snug">{html.escape(text)}</div>
      <div class="w-7 h-7 bg-wmgray-30 rounded-xl flex items-center justify-center text-xs font-bold text-wmgray-130 flex-shrink-0">You</div>
    </div>
    '''


def _sage_bubble(html_body: str) -> str:
    return f'''
    <div class="flex gap-2">
      <div class="w-7 h-7 sage-grad rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0">S</div>
      <div class="bg-wmgray-5 rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] leading-snug">{html_body}</div>
    </div>
    '''


RESPONSES = {
    "reprice": lambda: _sage_bubble('''
        <div>Sure! I found <strong>6 popular items</strong> where a small price drop could win you the sale.</div>
        <div class="mt-2 text-xs text-wmgray-100">It could earn you about <strong class="text-wmgreen-130">$7,200 more</strong> next month.</div>
        <a href="/plan/opp-1000" class="mt-2 inline-block text-xs font-bold text-wmblue-100 hover:underline">Take a look →</a>
    '''),
    "aging": lambda: _sage_bubble('''
        <div>You have <strong>7,208 items</strong> sitting in the warehouse over a year — and you're paying storage fees on them.</div>
        <div class="mt-2 text-xs text-wmgray-100">A clearance sale could turn them into <strong class="text-wmgreen-130">$157,000</strong> in your pocket.</div>
        <div class="mt-2 text-xs text-wmgray-100">⚠ This is a bigger change — let's talk through it together.</div>
        <a href="/plan/opp-1001" class="mt-2 inline-block text-xs font-bold text-wmblue-100 hover:underline">Take a look →</a>
    '''),
    "listings": lambda: _sage_bubble('''
        <div><strong>247 of your product pages</strong> are getting shoppers but not making the sale.</div>
        <div class="mt-2 text-xs text-wmgray-100">Better wording could turn 3\u20135 times more lookers into buyers — about <strong class="text-wmgreen-130">$44,800</strong> a week.</div>
        <a href="/plan/opp-1002" class="mt-2 inline-block text-xs font-bold text-wmblue-100 hover:underline">Take a look →</a>
    '''),
    "seo": lambda: _sage_bubble('''
        <div>I rewrote the titles and descriptions of your top 33 items so shoppers can find them more easily.</div>
        <div class="mt-2 text-xs text-wmgray-100">Sellers who use my suggestions average <strong class="text-wmgreen-130">15% more sales</strong>.</div>
        <a href="/plan/opp-1003" class="mt-2 inline-block text-xs font-bold text-wmblue-100 hover:underline">Take a look →</a>
    '''),
    "ad": lambda: _sage_bubble('''
        <div>Walmart gave you <strong>$1,250 in free ad money</strong> and it expires June 3.</div>
        <div class="mt-2 text-xs text-wmgray-100">I can use it on your most-loved items \u2014 likely <strong class="text-wmgreen-130">$8,750</strong> in extra sales.</div>
        <a href="/plan/opp-1004" class="mt-2 inline-block text-xs font-bold text-wmblue-100 hover:underline">Take a look →</a>
    '''),
    "promo": lambda: _sage_bubble('''
        <div>Walmart's big <strong>Memorial Day sale</strong> opens May 24, and 4 of your items qualify.</div>
        <div class="mt-2 text-xs text-wmgray-100">Joining could bring in roughly <strong class="text-wmgreen-130">$5,400</strong> over the weekend.</div>
        <a href="/plan/opp-1005" class="mt-2 inline-block text-xs font-bold text-wmblue-100 hover:underline">Take a look →</a>
    '''),
    "summary": lambda: _sage_bubble('''
        <div>Here's how things are going:</div>
        <ul class="mt-2 text-xs space-y-1 text-wmgray-130 list-disc pl-4">
          <li>I have <strong>7 ideas</strong> for you, worth about $241,000 in extra sales</li>
          <li>You're winning only 5 out of 100 sales right now — there's room to do much better</li>
          <li>Almost half of your product pages need a little love</li>
          <li>You have stuff sitting in the warehouse over a year</li>
        </ul>
        <a href="/inbox" class="mt-2 inline-block text-xs font-bold text-wmblue-100 hover:underline">See my ideas →</a>
    '''),
    "easy": lambda: _sage_bubble('''
        <div>Here are 2 quick wins you can knock out in 30 seconds:</div>
        <ul class="mt-2 text-xs space-y-2 text-wmgray-130">
          <li>\u2022 <a href="/plan/opp-1000" class="text-wmblue-100 font-bold hover:underline">Lower prices on 6 popular items</a> \u2014 +$7,200</li>
          <li>\u2022 <a href="/plan/opp-1003" class="text-wmblue-100 font-bold hover:underline">Improve wording on your top 33 items</a> \u2014 +$18,400</li>
        </ul>
    '''),
    "default": lambda: _sage_bubble('''
        <div>I can help you with <strong>prices, product listings, ads, promos, and search ranking</strong>.</div>
        <div class="mt-2 text-xs text-wmgray-100">Some things you can ask me:</div>
        <ul class="mt-1 text-xs text-wmgray-130 list-disc pl-4 space-y-0.5">
          <li>"What should I work on today?"</li>
          <li>"How am I doing this week?"</li>
          <li>"Find me easy wins"</li>
          <li>"What's losing me money?"</li>
        </ul>
    '''),
}


def _route(msg: str) -> str:
    m = msg.lower()
    if "easy" in m or "quick win" in m or "fast" in m:
        return RESPONSES["easy"]()
    if "reprice" in m or "buy box" in m or "buybox" in m or "price" in m:
        return RESPONSES["reprice"]()
    if "aging" in m or "clearance" in m or "warehouse" in m or "old stock" in m or "storage" in m:
        return RESPONSES["aging"]()
    if "listing" in m or "poor" in m or "quality" in m or "description" in m or "wording" in m:
        return RESPONSES["listings"]()
    if "seo" in m or "title" in m or "search" in m or "find" in m or "keyword" in m:
        return RESPONSES["seo"]()
    if "ad" in m or "credit" in m or "sponsored" in m or "campaign" in m or "free money" in m:
        return RESPONSES["ad"]()
    if "promo" in m or "memorial" in m or "sale" in m or "holiday" in m:
        return RESPONSES["promo"]()
    if "doing" in m or "how am i" in m or "summary" in m or "status" in m or "lose" in m or "losing" in m or "bleed" in m or "work on" in m or "today" in m:
        return RESPONSES["summary"]()
    return RESPONSES["default"]()


@router.post("/chat", response_class=HTMLResponse)
async def chat(message: str = Form(...)):
    return HTMLResponse(_user_bubble(message) + _route(message))
