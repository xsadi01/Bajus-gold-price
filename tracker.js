const fs = require('fs');
const path = require('path');
const fetch = require('node-fetch');
const { createCanvas } = require('canvas');

// গিটহাব সিক্রেটস বা লোকাল এনভায়রনমেন্ট থেকে ডাটা রিড করা
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;
const GITHUB_REPOSITORY = process.env.GITHUB_REPOSITORY || "your-username/your-repo"; 

const LAST_PRICE_FILE = path.join(__dirname, 'last_price.json');
const IMAGE_OUTPUT_FILE = path.join(__dirname, 'thermal_print.png');
const TARGET_URL = 'https://www.goldr.org/price.js?gttm';

const nameMapping = {
    "২২ ক্যারেট সোনার দাম": "22K Gold",
    "২১ ক্যারেট সোনার দাম": "21K Gold",
    "১৮ ক্যারেট সোনার দাম": "18K Gold",
    "সনাতন পদ্ধতির সোনার দাম": "Sanatan"
};

async function getLatestMarketData() {
    try {
        const response = await fetch(TARGET_URL, { headers: { 'User-Agent': 'Mozilla/5.0' } });
        const jsContent = await response.text();
        const goldMatch = jsContent.match(/GoldrPriceTable_goldData\s*=\s*(\[[\s\S]*?\]);/);
        const dateMatch = jsContent.match(/const datetime\s*=\s*"([^"]+)"/);

        if (!goldMatch) throw new Error("Format not found");

        const goldData = JSON.parse(goldMatch[1]);
        let updateDate = new Date().toISOString().split('T')[0];
        if (dateMatch && dateMatch[1]) updateDate = dateMatch[1].split(' ')[0];

        return { goldData, updateDate };
    } catch (error) {
        console.error("Data error:", error.message);
        return null;
    }
}

// থার্মাল প্রিন্টারের জন্য (384px চওড়া) B&W ইমেজ তৈরি করার ফাংশন
function generateThermalImage(data) {
    const width = 384; 
    const height = 450; 
    const canvas = createCanvas(width, height);
    const ctx = canvas.getContext('2d');

    // প্লেইন হোয়াইট ব্যাকগ্রাউন্ড
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = '#000000'; // পিওর ব্ল্যাক টেক্সট

    // হেডার
    ctx.font = 'bold 24px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('GOLD PRICE REPORT', width / 2, 40);

    ctx.font = '16px sans-serif';
    ctx.fillText(`Date: ${data.updateDate}`, width / 2, 70);

    // ডিভাইডার লাইন
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#000000';
    ctx.beginPath();
    ctx.moveTo(20, 90);
    ctx.lineTo(width - 20, 90);
    ctx.stroke();

    // গোল্ড রেট লুপ
    let currentY = 130;
    ctx.textAlign = 'left';

    data.goldData.forEach(item => {
        const name = nameMapping[item.n] || item.n;
        const gPrice = Number(item.bg_raw).toLocaleString('en-US', { maximumFractionDigits: 0 });
        const vPrice = Number(item.bv_raw).toLocaleString('en-US', { maximumFractionDigits: 0 });

        ctx.font = 'bold 20px sans-serif';
        ctx.fillText(`■ ${name}`, 20, currentY);
        
        ctx.font = '18px sans-serif';
        currentY += 28;
        ctx.fillText(`  Per Gram : ${gPrice} TK`, 20, currentY);
        currentY += 26;
        ctx.fillText(`  Per Vori : ${vPrice} TK`, 20, currentY);
        
        currentY += 40; 
    });

    // ফুটার ডিভাইডার
    ctx.beginPath();
    ctx.moveTo(20, currentY - 15);
    ctx.lineTo(width - 20, currentY - 15);
    ctx.stroke();

    ctx.font = 'italic 14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Printed by SSS', width / 2, currentY + 10);

    const buffer = canvas.toBuffer('image/png');
    fs.writeFileSync(IMAGE_OUTPUT_FILE, buffer);
    console.log("Thermal PNG image generated successfully.");
}

async function sendTelegramNotification(message, imageUrl) {
    if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
        console.log("Telegram tokens missing. Skipping message send.");
        return;
    }

    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
    const replyMarkup = {
        inline_keyboard: [[
            { text: "Download", url: imageUrl }
        ]]
    };

    try {
        await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: TELEGRAM_CHAT_ID,
                text: message,
                parse_mode: 'Markdown',
                reply_markup: replyMarkup
            })
        });
        console.log("Notification with download button sent to Telegram.");
    } catch (error) {
        console.error("Telegram error:", error);
    }
}

async function run() {
    const currentData = await getLatestMarketData();
    if (!currentData) return;

    // ১. গিটহাব অ্যাকশনের এরর এড়াতে দাম চেকের আগেই ইমেজ ফাইল তৈরি করে রাখা হলো
    generateThermalImage(currentData);

    let oldData = null;
    if (fs.existsSync(LAST_PRICE_FILE)) {
        try { oldData = JSON.parse(fs.readFileSync(LAST_PRICE_FILE, 'utf8')); } catch (e) { oldData = null; }
    }

    // ২. দাম পরিবর্তন না হলে এখানে স্ক্রিপ্ট স্টপ হবে, কিন্তু ইমেজ ফাইল গিটহাবে থেকে যাবে
    if (oldData && JSON.stringify(currentData.goldData) === JSON.stringify(oldData.goldData)) {
        console.log("No price change detected. Image updated but skipping telegram alert.");
        return;
    }

    let message = `🔔 *GOLD PRICE UPDATED*\n`;
    message += `📅 \`${currentData.updateDate}\`\n\n`;
    message += `\`Type     | Per Gram | Per Vori \`\n`;
    message += `\`---------------------------------\`\n`;
    
    currentData.goldData.forEach(item => {
        const name = nameMapping[item.n] || item.n;
        const paddedName = name.padEnd(8, ' ');
        const gPrice = Number(item.bg_raw).toLocaleString('en-US', { maximumFractionDigits: 0 }).padEnd(8, ' ');
        const vPrice = Number(item.bv_raw).toLocaleString('en-US', { maximumFractionDigits: 0 }).padEnd(8, ' ');
        message += `\`${paddedName} | ${gPrice} | ${vPrice} \`\n`;
    });

    const rawImageUrl = `https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/main/thermal_print.png?t=${Date.now()}`;

    await sendTelegramNotification(message, rawImageUrl);

    fs.writeFileSync(LAST_PRICE_FILE, JSON.stringify(currentData, null, 2), 'utf8');
}

run();
