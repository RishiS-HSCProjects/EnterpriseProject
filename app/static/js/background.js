const BackgroundHandler = {
    dayImage: '/static/assets/default-background-day.webp',
    nightImage: '/static/assets/default-background-night.webp',

    getCurrentImage() {
        const hour = new Date().getHours();
        return hour >= 6 && hour < 18 ? this.dayImage : this.nightImage;
    }
};
