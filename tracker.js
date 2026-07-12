const fs = require('fs');
const path = require('path');
const fetch = require('node-fetch');

// গিটহাব সিক্রেটস থেকে টোকেন ও চ্যাট আইডি রিড করবে
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

const LAST_PRICE_FILE = path.join(__dirname, 'last_price.json');
const TARGET_URL = 'https://www.goldr.org/price.js?gttm';

// বাংলা নামকে টেবিলের জন্য ছোট ও ইংলিশ ফরম্যাটে রূপান্তর করার ম্যাপ
const nameMapping = {
    "২২ ক্যারেট সোনার দাম": "22K",
    "২১ ক্যারেট সোনার দাম": "21K",
    "১৮ ক্যারেট সোনার দাম": "18K",
    "সনাতন পদ্ধতির সোনার দাম": "Sanatan"
};

// লাইভ ওয়েবসাইট থেকে স্ক্রিপ্ট ডাউনলোড করে ডেটা এক্সট্র্যাক্ট করার ফাংশন
async function getLatestMarketData() {
    try {
        const response = await fetch(TARGET_URL, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        });
        const jsContent = await response.text();

        // Regex দিয়ে goldData এবং datetime অংশটুকু খুঁজে বের করা
        const goldMatch = jsContent.match(/GoldrPriceTable_goldData\s*=\s*(\[[\s\S]*?\]);/);
        const dateMatch = jsContent.match(/const datetime\s*=\s*"([^"]+)"/);

        if (!goldMatch) {
            throw new Error("ওয়েবসাইট থেকে সোনার দামের ফরম্যাট খুঁজে পাওয়া যায়নি।");
        }

        const goldData = JSON.parse(goldMatch[1]);
        
        // ফুল ডেট-টাইম থেকে সময় বাদ দিয়ে শুধু ডেট (YYYY-MM-DD) আলাদা করা
        let updateDate = new Date().toISOString().split('T')[0];
        if (dateMatch && dateMatch[1]) {
            updateDate = dateMatch[1].split(' ')[0]; // স্পেস দিয়ে কেটে শুধু ডেট নেওয়া হলো
        }

        return { goldData, updateDate };
    } catch (error) {
        console.error("ডেটা সংগ্রহ করতে সমস্যা হয়েছে:", error.message);
        return null;
    }
}

async function sendTelegramMessage(message) {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
    try {
        await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: TELEGRAM_CHAT_ID,
                text: message,
                parse_mode: 'Markdown'
            })
        });
        console.log("টেলিগ্রামে নোটিফিকেশন পাঠানো হয়েছে।");
    } catch (error) {
        console.error("টেলিগ্রাম মেসেজ ফেইল্ড:", error);
    }
}

async function run() {
    const currentData = await getLatestMarketData();
    
    if (!currentData) {
        console.log("নতুন ডেটা পাওয়া যায়নি, স্কিপ করা হলো।");
        return;
    }

    let oldData = null;

    if (fs.existsSync(LAST_PRICE_FILE)) {
        try {
            oldData = JSON.parse(fs.readFileSync(LAST_PRICE_FILE, 'utf8'));
        } catch (e) {
            oldData = null;
        }
    }

    // শুধু goldData তুলনা করা হবে
    if (oldData && JSON.stringify(currentData.goldData) === JSON.stringify(oldData.goldData)) {
        console.log("সোনার দামের কোনো পরিবর্তন হয়নি।");
        return;
    }

    // দাম পরিবর্তন হলে মিনিমাল টেবিল ফরম্যাটে মেসেজ তৈরি করা
    let message = `🔔 *GOLD PRICE UPDATED*\n`;
    message += `📅 \`${currentData.updateDate}\`\n\n`;
    
    // টেবিলের হেডার
    message += `\`Type     | Per Gram | Per Vori \`\n`;
    message += `\`---------------------------------\`\n`;
    
    currentData.goldData.forEach(item => {
        const name = nameMapping[item.n] || item.n;
        
        const paddedName = name.padEnd(8, ' ');
        const gPrice = Number(item.bg_raw).toLocaleString('en-US', { maximumFractionDigits: 0 }).padEnd(8, ' ');
        const vPrice = Number(item.bv_raw).toLocaleString('en-US', { maximumFractionDigits: 0 }).padEnd(8, ' ');
        
        message += `\`${paddedName} | ${gPrice} | ${vPrice} ৳\`\n`;
    });

    await sendTelegramMessage(message);

    // বর্তমান ডেটা ফাইলে লিখে রাখা
    fs.writeFileSync(LAST_PRICE_FILE, JSON.stringify(currentData, null, 2), 'utf8');
    console.log("নতুন সোনার দাম টেবিল ফরম্যাটে সেভ ও পাঠানো হয়েছে।");
}

run();
