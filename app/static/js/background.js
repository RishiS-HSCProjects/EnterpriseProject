const BackgroundHandler = {
    dayImage: '/static/assets/default-background-day.webp',
    nightImage: '/static/assets/default-background-night.webp',

    init() {
        this.updateBackground();
        setInterval(() => this.updateBackground(), 60000); // Check every minute
    },

    isDaytime() {
        const hour = new Date().getHours();
        return hour >= 6 && hour < 18; // 6 AM to 6 PM
    },

    updateBackground() {
        const image = this.isDaytime() ? this.dayImage : this.nightImage;
        document.body.style.backgroundImage = `url('${image}')`;
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => BackgroundHandler.init());
} else {
    BackgroundHandler.init();
}
