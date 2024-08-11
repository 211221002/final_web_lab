document.addEventListener('DOMContentLoaded', function () {
    const notificationBell = document.getElementById('notificationBell');
    const notificationList = document.getElementById('notificationList');
    const notificationDropdown = document.getElementById('notificationDropdown');

    function fetchNotifications() {
        fetch('/notifications')
            .then(response => response.json())
            .then(data => {
                notificationList.innerHTML = '';
                let hasUnread = false;
                if (data.notifications.length > 0) {
                    // Reverse the notifications array to show latest first
                    data.notifications.reverse().forEach(notification => {
                        const notificationItem = document.createElement('a');
                        notificationItem.href = '#';
                        notificationItem.classList.add('dropdown-item');
                        notificationItem.textContent = notification.pemberitahuan;
                        notificationList.appendChild(notificationItem);
                        if (notification.status === 'belum dibaca') {
                            hasUnread = true;
                        }
                    });
                } else {
                    const noNotificationItem = document.createElement('a');
                    noNotificationItem.href = '#';
                    noNotificationItem.classList.add('dropdown-item');
                    noNotificationItem.textContent = 'No new notifications';
                    notificationList.appendChild(noNotificationItem);
                }
                if (hasUnread) {
                    notificationBell.style.color = 'red';
                } else {
                    notificationBell.style.color = '';
                }
            });
    }

    notificationDropdown.addEventListener('click', function () {
        // Mark notifications as read on the server
        fetch('/mark_notifications_as_read', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(() => {
            notificationBell.style.color = '';
            fetchNotifications();
        });
    });

    setInterval(fetchNotifications, 10000); // Check for notifications every 10 seconds
    fetchNotifications(); // Initial check
});
