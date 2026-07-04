# Artisan Hub

A LinkedIn-style platform for artists worldwide. Artists showcase their work (images, videos, text), production companies get verified badges, and everyone communicates via end-to-end encrypted chat.

## Tech Stack
- **Backend**: Node.js, Express, Socket.IO
- **Database**: MongoDB (Mongoose)
- **Auth**: JWT (JSON Web Tokens)
- **Chat**: Real-time via Socket.IO + E2E encryption (Web Crypto API)
- **Frontend**: HTML, TailwindCSS, Vanilla JS

## Setup
1. Clone the repo
2. `npm install`
3. Create `.env` with: `PORT=3000`, `MONGO_URI=your_mongodb_uri`, `JWT_SECRET=your_secret`
4. `npm start`
5. Open https://artisan-hub-fqi8.onrender.com/
