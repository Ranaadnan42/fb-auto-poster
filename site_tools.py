"""
BizTools Hub - free online tools (calculators). site_agent.py inhe har run par /tools/ mein banata hai.
Saara hisaab browser mein (JavaScript) hota hai - koi server/API nahi, hamesha free chalta hai.
Har tool ke saath likhi hui guide + FAQ hai taa ke Google ise "helpful page" samjhe, sirf form nahi.
"""

TOOL_CSS = """.tool{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;margin:22px 0}
.tool label{display:block;font-weight:600;font-size:15px;margin:12px 0 4px}
.tool input,.tool select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg);font:inherit;font-size:16px}
.tool .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 16px}
.tool .checks{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:6px 16px;margin-top:6px}
.tool .checks label{font-weight:400;display:flex;gap:8px;align-items:center;margin:4px 0}
.tool .checks input{width:auto}
.tool button{margin-top:16px;background:var(--brand);color:#fff;border:0;border-radius:10px;padding:12px 20px;font:inherit;font-weight:700;cursor:pointer}
.tool button.ghost{background:transparent;color:var(--brand);border:1px solid var(--brand);margin-left:8px}
.result{margin-top:20px;display:none}.result.show{display:block}
.big{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:12px 0}
.big div{background:var(--brand2);border-radius:12px;padding:12px 14px}.big b{display:block;font-size:24px;color:var(--brand)}
.big span{font-size:13px;color:var(--muted)}.note{font-size:13px;color:var(--muted)}
.ing{display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr auto;gap:6px;align-items:end;margin-bottom:6px}
.ing{border-bottom:1px solid var(--line);padding-bottom:8px}.ing label{margin:0;font-weight:400}.ing label span{display:block;font-size:12px;color:var(--muted)}
.ing input{padding:8px}.ing .x{background:transparent;color:var(--muted);border:1px solid var(--line);margin:0;padding:8px 12px}
@media (max-width:640px){.ing{grid-template-columns:1fr 1fr}.ing label:first-child{grid-column:1/-1}.ing .x{grid-column:1/-1;justify-self:end}}
.tcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;margin:16px 0 30px}
.tcards a{border:1px solid var(--line);background:var(--card);border-radius:14px;padding:16px;text-decoration:none;color:var(--fg)}
.tcards a b{display:block;font-size:18px;margin-bottom:4px}.tcards a span{color:var(--muted);font-size:14px}
.toolbox{border:2px dashed var(--brand);border-radius:14px;padding:14px 18px;margin:22px 0}"""

# Chhota helper JS: paise ka format aur result dikhana
BASE_JS = """function $(i){return document.getElementById(i)}
function num(i){var v=parseFloat(($(i)||{}).value);return isNaN(v)?0:v}
function money(v){return '$'+Math.round(v).toLocaleString('en-US')}
function range(a,b){return money(a)+' - '+money(b)}
function show(id,html){var r=$(id);r.innerHTML=html;r.classList.add('show');r.scrollIntoView({behavior:'smooth',block:'nearest'})}
function stat(label,val){return '<div><span>'+label+'</span><b>'+val+'</b></div>'}"""

# ----------------------------------------------------------------------------------------------
POS_FORM = """<div class="tool" id="calc">
<div class="row">
<div><label for="biz">Business type</label><select id="biz">
<option value="retail">Retail shop</option><option value="restaurant">Restaurant</option>
<option value="cafe">Cafe / coffee shop</option><option value="grocery">Grocery / supermarket</option>
<option value="salon">Salon / services</option></select></div>
<div><label for="term">Number of checkout terminals</label><input id="term" type="number" min="1" max="50" value="1"></div>
<div><label for="loc">Number of locations</label><input id="loc" type="number" min="1" max="20" value="1"></div>
<div><label for="sales">Monthly card sales (USD)</label><input id="sales" type="number" min="0" step="500" value="15000"></div>
</div>
<label>Hardware you still need to buy (per terminal)</label>
<div class="checks">
<label><input type="checkbox" id="h_pc" checked> Touch-screen terminal / PC</label>
<label><input type="checkbox" id="h_prn" checked> Receipt printer</label>
<label><input type="checkbox" id="h_drw" checked> Cash drawer</label>
<label><input type="checkbox" id="h_scan"> Barcode scanner</label>
<label><input type="checkbox" id="h_card" checked> Card reader</label>
<label><input type="checkbox" id="h_kit"> Kitchen printer / display</label>
</div>
<div class="row">
<div><label for="rate">Card processing rate (%)</label><input id="rate" type="number" min="0" max="6" step="0.1" value="2.7"></div>
<div><label for="years">Compare over (years)</label><select id="years"><option>1</option><option>2</option><option selected>3</option><option>5</option></select></div>
</div>
<button type="button" onclick="calc()">Calculate POS cost</button>
<div class="result" id="out" aria-live="polite"></div>
</div>"""

POS_JS = """var HW={h_pc:[500,1400],h_prn:[150,350],h_drw:[80,150],h_scan:[50,200],h_card:[50,300],h_kit:[250,600]};
var SAAS={retail:[50,110],restaurant:[70,165],cafe:[60,130],grocery:[70,150],salon:[40,100]};
var LIC={retail:[300,1200],restaurant:[500,1800],cafe:[400,1400],grocery:[500,1800],salon:[250,900]};
function calc(){
 var t=Math.max(1,num('term')),l=Math.max(1,num('loc')),y=parseInt($('years').value),b=$('biz').value;
 var hw=[0,0];for(var k in HW){if($(k).checked){hw[0]+=HW[k][0];hw[1]+=HW[k][1];}}
 hw=[hw[0]*t,hw[1]*t];
 var fee=num('sales')*num('rate')/100;
 var sm=[SAAS[b][0]*t,SAAS[b][1]*t];
 var saasTot=[hw[0]+sm[0]*12*y,hw[1]+sm[1]*12*y];
 var lic=[LIC[b][0]*t,LIC[b][1]*t],sup=[lic[0]*0.15,lic[1]*0.2];
 var licTot=[hw[0]+lic[0]+sup[0]*Math.max(0,y-1),hw[1]+lic[1]+sup[1]*Math.max(0,y-1)];
 var cheaper=(licTot[0]+licTot[1])<(saasTot[0]+saasTot[1])?'one-time license':'monthly subscription';
 show('out','<h3>Your estimate ('+t+' terminal'+(t>1?'s':'')+(l>1?', '+l+' locations':'')+')</h3>'+
 '<div class="big">'+stat('Hardware (one-time)',range(hw[0],hw[1]))+stat('Card fees per month',money(fee))+'</div>'+
 '<table><thead><tr><th></th><th>Monthly subscription (cloud)</th><th>One-time license</th></tr></thead><tbody>'+
 '<tr><td>Software upfront</td><td>$0</td><td>'+range(lic[0],lic[1])+'</td></tr>'+
 '<tr><td>Software per month</td><td>'+range(sm[0],sm[1])+'</td><td>$0 (optional support '+range(sup[0]/12,sup[1]/12)+')</td></tr>'+
 '<tr><td><strong>Total over '+y+' year'+(y>1?'s':'')+'</strong></td><td><strong>'+range(saasTot[0],saasTot[1])+'</strong></td><td><strong>'+range(licTot[0],licTot[1])+'</strong></td></tr>'+
 '<tr><td>Card processing fees (same for both)</td><td colspan="2">'+money(fee*12*y)+' over '+y+' year'+(y>1?'s':'')+'</td></tr>'+'</tbody></table><p>Over '+y+' year'+(y>1?'s':'')+', a <strong>'+cheaper+'</strong> usually costs less for a setup like yours. '+
 'Totals include hardware and software; card fees are listed separately because they depend on your payment provider, not the POS model.</p><p class="note">Estimates only, based on typical 2026 market price ranges. Real quotes vary by vendor, country and contract.</p>');
}"""

POS_GUIDE = """<h2>How this POS cost calculator works</h2>
<p>A point-of-sale system has three costs that many sellers quote separately: the <strong>hardware</strong>, the <strong>software</strong> and the <strong>card processing fees</strong>. The calculator adds all three so you can see the real total cost of ownership, not just the monthly price on a pricing page.</p>
<ul><li><strong>Hardware</strong> is a one-time purchase per checkout: a touch-screen terminal or PC, receipt printer, cash drawer, card reader, and for some businesses a barcode scanner or kitchen printer.</li>
<li><strong>Software</strong> is either a monthly subscription per terminal (most cloud POS brands) or a one-time license with optional yearly support.</li>
<li><strong>Card processing</strong> is a percentage of your card sales, usually between 2.3% and 3.5% depending on the provider and card type.</li></ul>
<h2>Subscription vs one-time license: which is cheaper?</h2>
<p>Subscriptions cost little to start and include updates and cloud backups, which suits new businesses and multi-location chains. A one-time license costs more on day one but often becomes cheaper after 18-30 months, which is why many shop owners in markets like Saudi Arabia, the UAE and Pakistan prefer it. Change the "compare over" years in the tool to see where the two lines cross for your setup.</p>
<h3>Hidden costs to ask every POS vendor about</h3>
<ul><li>Is card processing locked to their own payment provider?</li><li>Are there extra fees for inventory, loyalty, online ordering or extra users?</li>
<li>What happens to your sales data if you cancel?</li><li>Does the software keep working when the internet goes down?</li>
<li>Does it support your country's e-invoicing or tax rules (for example ZATCA in Saudi Arabia)?</li></ul>"""

POS_FAQ = [
    {"q": "How much does a POS system cost for a small business?",
     "a": "For one checkout, expect roughly $800-$2,500 for hardware, plus either about $50-$165 per month for subscription software or a one-time license of roughly $300-$1,800. Card processing fees come on top and depend on your sales."},
    {"q": "Is a cloud POS better than a one-time license POS?",
     "a": "Neither is always better. Cloud POS is cheaper to start and easy to manage across locations; a one-time license is often cheaper over three or more years and does not depend on a monthly payment. Compare total cost and offline support."},
    {"q": "Can I use my existing computer or tablet as a POS?",
     "a": "Often yes. Many POS apps run on a normal Windows PC, iPad or Android tablet, which can save $500 or more per terminal. Untick the terminal option in the calculator to see the difference."},
    {"q": "Are these POS prices exact?",
     "a": "No. They are typical market ranges to help you budget and compare quotes. Prices vary by brand, country, contract length and promotions, so always confirm with the vendor."},
]

# ----------------------------------------------------------------------------------------------
FOOD_FORM = """<div class="tool" id="calc">
<div class="row">
<div><label for="dish">Dish name</label><input id="dish" type="text" value="Chicken burger" maxlength="60"></div>
<div><label for="portions">Portions this recipe makes</label><input id="portions" type="number" min="1" value="1"></div>
</div>
<div id="ings"></div>
<button type="button" class="ghost" style="margin-left:0" onclick="addIng()">+ Add ingredient</button>
<p class="note">Use the same unit for pack size and amount used (for example both in grams, or both in pieces).</p>
<div class="row">
<div><label for="target">Target food cost %</label><input id="target" type="number" min="5" max="80" value="30"></div>
<div><label for="price">Your current menu price ($, optional)</label><input id="price" type="number" min="0" step="0.25" value=""></div>
</div>
<button type="button" onclick="calc()">Calculate food cost</button>
<div class="result" id="out" aria-live="polite"></div>
</div>"""

FOOD_JS = """var START=[['Burger bun',3.5,6,1,100],['Chicken breast (g)',9,1000,150,90],['Cheese slice',4,12,1,100],['Lettuce (g)',2,500,20,80],['Sauce (g)',5,1000,30,100]];
function addIng(v){v=v||['',0,1,0,100];var d=document.createElement('div');d.className='ing';
 var f=['text','number','number','number','number'],ph=['Ingredient','Pack price ($)','Pack size','Used in recipe','Usable yield %'];
 for(var i=0;i<5;i++){var w=document.createElement('label');var c=document.createElement('span');c.textContent=ph[i];var e=document.createElement('input');e.type=f[i];e.value=v[i]===0&&i>0?'':v[i];if(i>0){e.min='0';e.step='any';}w.appendChild(c);w.appendChild(e);d.appendChild(w);}
 var x=document.createElement('button');x.type='button';x.className='x';x.textContent='\\u00d7';x.setAttribute('aria-label','Remove');x.onclick=function(){d.remove();};d.appendChild(x);
 $('ings').appendChild(d);}
START.forEach(addIng);
function calc(){
 var rows=document.querySelectorAll('#ings .ing'),total=0,lines=[];
 rows.forEach(function(r){var e=r.querySelectorAll('input');var name=e[0].value||'Ingredient';
  var price=parseFloat(e[1].value)||0,size=parseFloat(e[2].value)||0,used=parseFloat(e[3].value)||0,y=parseFloat(e[4].value)||100;
  if(size<=0||used<=0)return;var c=price/size*used/(Math.min(100,Math.max(1,y))/100);total+=c;lines.push([name,c]);});
 var p=Math.max(1,num('portions')),cost=total/p,t=Math.min(80,Math.max(5,num('target')||30)),sug=cost/(t/100),cur=num('price');
 var tb=document.createElement('tbody');lines.forEach(function(l){var tr=document.createElement('tr');var a=document.createElement('td');a.textContent=l[0];var b=document.createElement('td');b.textContent='$'+(l[1]/p).toFixed(2);tr.appendChild(a);tr.appendChild(b);tb.appendChild(tr);});
 var h='<h3></h3><div class="big">'+stat('Cost per portion','$'+cost.toFixed(2))+stat('Suggested price at '+t+'%','$'+sug.toFixed(2));
 if(cur>0){var pct=cost/cur*100;h+=stat('Your food cost %',pct.toFixed(1)+'%')+stat('Gross profit per plate','$'+(cur-cost).toFixed(2));}
 h+='</div><table><thead><tr><th>Ingredient</th><th>Cost per portion</th></tr></thead></table>';
 if(cur>0){var pct2=cost/cur*100;h+='<p>'+(pct2>t+3?'Your food cost is above your target. Consider a smaller portion, a cheaper supplier or a price of about $'+sug.toFixed(2)+'.':(pct2<t-8?'Your food cost is well below target - good margin. Check the portion still feels like value to customers.':'Your food cost is close to your target.'))+'</p>';}
 h+='<p class="note">Food cost covers ingredients only. Labour, rent, packaging and waste are extra, which is why most restaurants aim for 25-35%.</p>';
 show('out',h);$('out').querySelector('h3').textContent='Food cost for '+($('dish').value||'your dish');$('out').querySelector('table').appendChild(tb);
}"""

FOOD_GUIDE = """<h2>How to calculate food cost for a menu item</h2>
<p>Food cost is the ingredient cost of one portion, divided by its menu price. The formula is simple, but getting the ingredient costs right is where most owners make mistakes.</p>
<ol><li><strong>Cost each ingredient per unit:</strong> pack price divided by pack size. A 1,000 g pack of chicken at $9 costs $0.009 per gram.</li>
<li><strong>Adjust for yield:</strong> trimming, bones, peel and cooking loss mean you use more than you serve. If only 90% of the chicken is usable, divide by 0.9.</li>
<li><strong>Multiply by the amount used</strong> in the recipe and add up all ingredients, including sauces, oil and garnish.</li>
<li><strong>Divide by portions</strong> if the recipe makes more than one serving.</li>
<li><strong>Price the dish:</strong> menu price = portion cost / target food cost %. At a 30% target, a $2.40 portion should sell for about $8.00.</li></ol>
<h2>What is a good food cost percentage?</h2>
<p>Most restaurants aim for 25-35% overall. Coffee and drinks often run 10-20%, while steak or seafood dishes can sit at 35-40% because the cash profit per plate is still high. Look at both the percentage and the gross profit in dollars before changing a price.</p>
<h3>Ways to lower food cost without raising prices</h3>
<ul><li>Weigh portions for your most-sold dishes and train staff on them.</li><li>Re-price recipes whenever supplier prices change, not once a year.</li>
<li>Use trim from one dish in another (soups, sauces, staff meals).</li><li>Track waste daily; a POS with inventory tracking makes this much easier.</li></ul>"""

FOOD_FAQ = [
    {"q": "What is the formula for food cost percentage?",
     "a": "Food cost % = (ingredient cost of one portion / menu price) x 100. For example, a dish that costs $3 to make and sells for $10 has a 30% food cost."},
    {"q": "How do I set a menu price from food cost?",
     "a": "Divide the portion cost by your target food cost as a decimal. A $2.50 portion at a 30% target gives $2.50 / 0.30 = about $8.35, which you can round to a menu-friendly price."},
    {"q": "Does food cost include labour and packaging?",
     "a": "No. Food cost is ingredients only. Packaging is often tracked separately, and labour plus food together are called prime cost, which many restaurants keep under about 60-65% of sales."},
    {"q": "Why should I include yield percentage?",
     "a": "Because you rarely serve 100% of what you buy. Trimming, peeling and cooking loss raise the true cost per usable gram, and ignoring it makes dishes look more profitable than they are."},
]

# ----------------------------------------------------------------------------------------------
WEB_FORM = """<div class="tool" id="calc">
<div class="row">
<div><label for="type">Type of website</label><select id="type">
<option value="brochure">Simple business site (1-5 pages)</option><option value="business" selected>Small business site (6-15 pages)</option>
<option value="shop">Online store (e-commerce)</option><option value="booking">Booking / appointment site</option></select></div>
<div><label for="who">Who builds it</label><select id="who">
<option value="diy">Do it yourself (website builder)</option><option value="free" selected>Freelancer</option><option value="agency">Agency</option></select></div>
<div><label for="pages">Number of pages</label><input id="pages" type="number" min="1" max="200" value="8"></div>
<div><label for="prod">Products (online store only)</label><input id="prod" type="number" min="0" max="5000" value="0"></div>
</div>
<label>Features</label>
<div class="checks">
<label><input type="checkbox" id="f_logo"> Logo &amp; branding</label>
<label><input type="checkbox" id="f_copy"> Professional copywriting</label>
<label><input type="checkbox" id="f_seo" checked> Basic SEO setup</label>
<label><input type="checkbox" id="f_blog"> Blog</label>
<label><input type="checkbox" id="f_lang"> Second language</label>
<label><input type="checkbox" id="f_pay"> Online payments</label>
<label><input type="checkbox" id="f_book"> Booking calendar</label>
<label><input type="checkbox" id="f_chat"> WhatsApp / AI chat</label>
</div>
<button type="button" onclick="calc()">Estimate website cost</button>
<div class="result" id="out" aria-live="polite"></div>
</div>"""

WEB_JS = """var BASE={brochure:{diy:[0,150],free:[400,1500],agency:[2000,6000]},business:{diy:[100,300],free:[1200,4000],agency:[5000,15000]},
 shop:{diy:[200,600],free:[2500,8000],agency:[10000,40000]},booking:{diy:[150,400],free:[1800,5000],agency:[7000,20000]}};
var FEAT={f_logo:[100,800],f_copy:[300,1500],f_seo:[200,800],f_blog:[150,600],f_lang:[300,1500],f_pay:[200,1000],f_book:[300,1200],f_chat:[100,800]};
var RUN={diy:[200,600],free:[60,400],agency:[60,600]};
var PAGES={brochure:5,business:12,shop:15,booking:10};
function calc(){
 var t=$('type').value,w=$('who').value,b=BASE[t][w].slice(),m=w==='diy'?0.15:(w==='free'?1:2.2);
 var extra=Math.max(0,num('pages')-PAGES[t]);var per=w==='diy'?[0,0]:(w==='free'?[50,150]:[150,400]);
 b[0]+=extra*per[0];b[1]+=extra*per[1];
 if(t==='shop'){var pr=Math.max(0,num('prod')-20);b[0]+=pr*(w==='diy'?0:1);b[1]+=pr*(w==='diy'?0:4);}
 for(var k in FEAT){if($(k).checked){b[0]+=FEAT[k][0]*m;b[1]+=FEAT[k][1]*m;}}
 var r=RUN[w].slice();if(t==='shop'){r[0]+=150;r[1]+=900;}
 var main=[b[0]+r[0],b[1]+r[1]];
 show('out','<h3>Your website estimate</h3><div class="big">'+stat('Build cost (one-time)',range(b[0],b[1]))+stat('Running cost per year',range(r[0],r[1]))+stat('First-year total',range(main[0],main[1]))+'</div>'+
 '<p>Running costs cover your domain (about $10-$20 a year), hosting or a builder plan, and for online stores, apps and payment extras. '+(w==='diy'?'With a website builder the main cost is your own time - plan on 15-40 hours for a good result.':'Ask for a fixed quote that lists every page and feature so the price cannot grow later.')+'</p>'+
 '<p class="note">Estimates only, based on typical 2026 prices in the US, UK and Europe. Rates in other regions can be much lower.</p>');
}"""

WEB_GUIDE = """<h2>What decides the cost of a small business website?</h2>
<p>Website prices range from almost nothing to tens of thousands of dollars because "a website" can mean very different jobs. Four things move the price the most:</p>
<ul><li><strong>Who builds it.</strong> A website builder (Wix, Squarespace, Shopify and similar) is cheapest in money but costs your time. Freelancers sit in the middle; agencies charge more for strategy, design and project management.</li>
<li><strong>The type of site.</strong> A five-page brochure site is far simpler than an online store with payments, shipping rules and stock levels.</li>
<li><strong>Content.</strong> Writing text, taking photos and creating a logo are often bigger jobs than the build itself.</li>
<li><strong>Features.</strong> Booking, payments, multiple languages and chat each add setup and testing time.</li></ul>
<h2>One-time build vs yearly running costs</h2>
<p>Every website has running costs after launch: the domain name, hosting or a builder subscription, security updates and small edits. Budget for them from the start - a cheap build with expensive monthly add-ons can cost more over three years than a fixed-price custom site.</p>
<h3>Questions to ask before you hire someone</h3>
<ul><li>Will the domain and hosting be registered in my name?</li><li>Can I edit text and photos myself after launch?</li>
<li>Is basic SEO (titles, descriptions, speed, mobile layout) included?</li><li>What does a small change cost after the project ends?</li></ul>"""

WEB_FAQ = [
    {"q": "How much does a small business website cost in 2026?",
     "a": "Roughly $100-$600 a year if you build it yourself with a website builder, about $1,000-$5,000 with a freelancer, and $5,000-$15,000 or more with an agency. Online stores and booking sites cost more."},
    {"q": "What are the yearly costs of running a website?",
     "a": "Usually a domain name at about $10-$20 a year plus hosting or a builder plan, which can range from about $60 to $600 a year. Online stores often pay extra for apps, themes and payment features."},
    {"q": "Is a website builder good enough for a small business?",
     "a": "For many service businesses, yes. Builders are fast and affordable. A custom site makes more sense when you need special features, many languages, tight integration with your POS or better long-term control."},
    {"q": "Are these website prices exact?",
     "a": "No. They are typical ranges to help you plan and compare quotes. Prices change by country, provider and scope, so use the result as a starting point for discussions."},
]

# ----------------------------------------------------------------------------------------------
APP_FORM = """<div class="tool" id="calc">
<div class="row">
<div><label for="plat">Platforms</label><select id="plat">
<option value="one">iOS or Android only</option><option value="cross" selected>iOS + Android (cross-platform)</option><option value="native">iOS + Android (two native apps)</option></select></div>
<div><label for="design">Design level</label><select id="design">
<option value="basic">Template / basic</option><option value="custom" selected>Custom design</option><option value="premium">Premium with animations</option></select></div>
<div><label for="team">Team &amp; hourly rate</label><select id="team">
<option value="25,50">Freelancer / offshore ($25-$50/h)</option><option value="50,100" selected>Small studio ($50-$100/h)</option><option value="100,180">US/UK agency ($100-$180/h)</option></select></div>
</div>
<label>Features</label>
<div class="checks">
<label><input type="checkbox" id="a_login" checked> User login &amp; profiles</label>
<label><input type="checkbox" id="a_admin" checked> Admin panel</label>
<label><input type="checkbox" id="a_push" checked> Push notifications</label>
<label><input type="checkbox" id="a_pay"> In-app payments</label>
<label><input type="checkbox" id="a_order"> Ordering / cart</label>
<label><input type="checkbox" id="a_book"> Booking / appointments</label>
<label><input type="checkbox" id="a_loyal"> Loyalty points / rewards</label>
<label><input type="checkbox" id="a_map"> Maps &amp; location</label>
<label><input type="checkbox" id="a_chat"> Chat / messaging</label>
<label><input type="checkbox" id="a_off"> Works offline</label>
<label><input type="checkbox" id="a_pos"> Connect to POS / inventory</label>
<label><input type="checkbox" id="a_ai"> AI features (chatbot, recommendations)</label>
</div>
<button type="button" onclick="calc()">Estimate app cost</button>
<div class="result" id="out" aria-live="polite"></div>
</div>"""

APP_JS = """var FH={a_login:[40,80],a_admin:[60,140],a_push:[15,35],a_pay:[40,90],a_order:[60,140],a_book:[50,120],a_loyal:[40,100],a_map:[30,70],a_chat:[60,150],a_off:[40,110],a_pos:[50,140],a_ai:[40,120]};
function calc(){
 var h=[120,200];for(var k in FH){if($(k).checked){h[0]+=FH[k][0];h[1]+=FH[k][1];}}
 var d={basic:1,custom:1.25,premium:1.55}[$('design').value],p={one:1,cross:1.3,native:1.85}[$('plat').value];
 h=[h[0]*d*p*1.2,h[1]*d*p*1.2];
 var r=$('team').value.split(',').map(Number),c=[h[0]*r[0],h[1]*r[1]];
 var weeks=[Math.ceil(h[0]/80),Math.ceil(h[1]/80)];
 show('out','<h3>Your app estimate</h3><div class="big">'+stat('Development cost',range(c[0],c[1]))+stat('Estimated hours',Math.round(h[0])+' - '+Math.round(h[1]))+
 stat('Timeline (2-person team)',weeks[0]+' - '+weeks[1]+' weeks')+stat('Yearly maintenance',range(c[0]*0.15,c[1]*0.2))+'</div>'+
 '<p>Store fees are extra: Apple charges $99 per year and Google Play a one-time $25. Servers, maps and messaging services usually add about $20-$300 per month depending on users.</p>'+
 '<p>To cut cost, launch with the 3-4 features customers need most, then add the rest after real feedback.</p>'+
 '<p class="note">Estimates only, based on typical hours for each feature and common 2026 hourly rates. A detailed quote needs a written feature list.</p>');
}"""

APP_GUIDE = """<h2>How app development cost is estimated</h2>
<p>Developers price apps by time: the hours needed for each screen and feature, multiplied by an hourly rate. This calculator uses typical hour ranges per feature, then adjusts for design level and the number of platforms.</p>
<ul><li><strong>Platforms:</strong> one cross-platform codebase (Flutter or React Native) usually costs about 30% more than a single platform, while two separate native apps can cost close to double.</li>
<li><strong>Features:</strong> login, payments, chat and admin panels each need screens, a server side and testing. Chat and ordering are among the biggest.</li>
<li><strong>Design:</strong> custom branding and animations take more design and front-end time than a template.</li>
<li><strong>Team location:</strong> the same app can cost three to four times more with a US or UK agency than with an experienced offshore team.</li></ul>
<h2>Costs after launch</h2>
<p>Plan roughly 15-20% of the build cost per year for updates, new phone OS versions, bug fixes and server costs. Apps that are never updated start breaking within a year or two as iOS and Android change.</p>
<h3>Does a small business need an app or just a website?</h3>
<p>If customers order or book from you often (restaurants, salons, gyms, repeat retail), an app with loyalty rewards and push notifications can pay for itself. If most visitors come once, a fast mobile-friendly website is usually the better first investment.</p>"""

APP_FAQ = [
    {"q": "How much does it cost to build an app for a small business?",
     "a": "A simple app with a few features often costs about $5,000-$25,000 with a freelancer or small studio, and $40,000-$150,000 or more with a US or UK agency. The feature list and platforms matter more than anything else."},
    {"q": "How long does it take to build an app?",
     "a": "A focused first version usually takes about 6-16 weeks. Apps with ordering, payments, chat and admin panels take longer, especially if they must connect to an existing POS or inventory system."},
    {"q": "Is cross-platform cheaper than native?",
     "a": "Usually yes. One cross-platform codebase serves iOS and Android and typically costs much less than building two native apps, with good performance for most business apps."},
    {"q": "Are these app cost estimates exact?",
     "a": "No. They are planning ranges based on typical hours and rates. A real quote depends on your exact screens, integrations and the team you choose."},
]

# ----------------------------------------------------------------------------------------------
# slug: (naam, meta title, meta description, short card text, form, js, guide, faq, kis category/topic se link)
TOOLS = {
    "pos-system-cost-calculator": {
        "name": "POS System Cost Calculator",
        "title": "POS System Cost Calculator (Free) - Hardware, Software & Fees",
        "desc": "Free POS system cost calculator: estimate hardware, monthly vs one-time software and card fees, and compare total cost over 1-5 years for your shop or restaurant.",
        "card": "Compare subscription vs one-time POS cost, with hardware and card fees.",
        "h1": "POS System Cost Calculator",
        "lead": "Estimate what a point-of-sale system will really cost your business - hardware, software and card processing fees - and see whether a monthly subscription or a one-time license is cheaper over time.",
        "form": POS_FORM, "js": POS_JS, "guide": POS_GUIDE, "faq": POS_FAQ,
        "categories": ["pos-systems"], "words": ["pos", "point of sale", "cash register", "checkout", "inventory", "retail"],
    },
    "restaurant-food-cost-calculator": {
        "name": "Restaurant Food Cost Calculator",
        "title": "Restaurant Food Cost Calculator - Plate Cost & Menu Price",
        "desc": "Free food cost calculator for restaurants and cafes: work out the cost per plate with yield, your food cost percentage and a suggested menu price.",
        "card": "Work out cost per plate, food cost % and the right menu price.",
        "h1": "Restaurant Food Cost Calculator",
        "lead": "Add the ingredients of any dish to find its exact cost per portion, your food cost percentage and a menu price that hits your target margin.",
        "form": FOOD_FORM, "js": FOOD_JS, "guide": FOOD_GUIDE, "faq": FOOD_FAQ,
        "categories": [], "words": ["restaurant", "food", "menu", "cafe", "coffee", "kitchen", "bakery", "catering"],
    },
    "website-cost-calculator": {
        "name": "Website Cost Calculator",
        "title": "Website Cost Calculator for Small Business (Free Estimate)",
        "desc": "Free website cost calculator: estimate the build price and yearly running costs of a small business website or online store, DIY vs freelancer vs agency.",
        "card": "Estimate build and yearly costs: DIY, freelancer or agency.",
        "h1": "Website Cost Calculator",
        "lead": "Get a realistic price range for your business website or online store, plus the yearly running costs most quotes leave out.",
        "form": WEB_FORM, "js": WEB_JS, "guide": WEB_GUIDE, "faq": WEB_FAQ,
        "categories": ["websites"], "words": ["website", "online store", "ecommerce", "seo", "web design", "domain"],
    },
    "app-development-cost-calculator": {
        "name": "App Development Cost Calculator",
        "title": "App Development Cost Calculator - Free Estimate by Feature",
        "desc": "Free app cost calculator: pick platforms, design and features to estimate the cost, hours, timeline and yearly maintenance of a small business mobile app.",
        "card": "Pick features and platforms to estimate app cost and timeline.",
        "h1": "App Development Cost Calculator",
        "lead": "Choose your platforms, design level and features to estimate how much a mobile app for your business will cost to build and maintain.",
        "form": APP_FORM, "js": APP_JS, "guide": APP_GUIDE, "faq": APP_FAQ,
        "categories": ["mobile-apps"], "words": ["app", "loyalty", "ordering", "mobile"],
    },
}


def tool_for_post(p):
    """Article ke topic ke hisaab se sab se munasib tool (ya None)."""
    text = f"{p.get('title', '')} {p.get('keyword', '')} {' '.join(p.get('tags', []))}".lower()
    best, score = None, 0
    for slug, t in TOOLS.items():
        s = sum(2 for w in t["words"] if w in text) + (3 if p.get("category") in t["categories"] else 0)
        if s > score:
            best, score = slug, s
    return best
