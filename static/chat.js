// Fetch user data and populate chat modal
function loadChatModal() {
    fetch('/get_user_data', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(userData => {
            if (!userData.error) {
                currentUser = userData.name;

                fetch('/get_user_projects_data', {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                    .then(response => response.json())
                    .then(data => {
                        const projectList = document.querySelector('.list-group.chat-item');
                        projectList.innerHTML = '';

                        data.user_project_data.forEach(function (project) {
                            const projectItem = document.createElement('li');
                            projectItem.classList.add('list-group-item');
                            projectItem.textContent = project.project_name;
                            projectItem.setAttribute('data-project-id', project._id);
                            projectItem.setAttribute('data-project-name', project.project_name); // store project name

                            projectItem.addEventListener('click', function () {
                                const projectId = projectItem.getAttribute('data-project-id');
                                const projectName = projectItem.getAttribute('data-project-name'); // get project name
                                document.getElementById('chatRoomModal').setAttribute('data-project-id', projectId);
                                document.getElementById('chatRoomModalLabel').innerText = `Chat Room - ${projectName}`; // update modal title

                                fetch('/get_project_messages/' + projectId, {
                                    method: 'GET',
                                    headers: {
                                        'Content-Type': 'application/json'
                                    }
                                })
                                    .then(response => response.json())
                                    .then(data => {
                                        const chatMessages = document.getElementById('chatMessages');
                                        chatMessages.innerHTML = '';

                                        data.messages.forEach(function (message) {
                                            const messageItem = document.createElement('li');
                                            messageItem.classList.add('list-group-item');
                                            if (message.sender === currentUser) {
                                                messageItem.classList.add('sent');
                                            }
                                            messageItem.innerHTML = `<strong>${message.sender}: </strong>${message.text}`;
                                            chatMessages.appendChild(messageItem);
                                        });
                                    })
                                    .catch(error => {
                                        console.error('Error:', error);
                                    });

                                $('#chatRoomModal').modal('show');
                            });

                            projectList.appendChild(projectItem);
                        });
                    })
                    .catch(error => {
                        console.error('Error:', error);
                    });
            } else {
                console.error('Error:', userData.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

document.addEventListener('DOMContentLoaded', function () {
    // Load chat modal on page load
    loadChatModal();

    // Handle opening chat modal from any trigger button
    const chatButtons = document.querySelectorAll('.btn-primary[data-toggle="modal"]');
    chatButtons.forEach(button => {
        button.addEventListener('click', function () {
            $('#chatModal').modal('show');
        });
    });
});

document.addEventListener('DOMContentLoaded', function () {
    // When chatRoomModal is shown, hide chatModal if it's visible
    $('#chatRoomModal').on('show.bs.modal', function (e) {
        $('#chatModal').modal('hide');
    });
});

document.addEventListener('DOMContentLoaded', function () {
    const chatButton = document.querySelector('.btn-primary[data-target="#chatModal"]');
    const sendMessageButton = document.getElementById('sendMessageButton');
    const sendFileButton = document.getElementById('sendFileButton');
    const chatInput = document.getElementById("chatInput");
    const chatFileInput = document.getElementById("chatFileInput");
    let currentUser;

    chatButton.addEventListener('click', function () {
        fetch('/get_user_data', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(userData => {
            if (!userData.error) {
                currentUser = userData.name;
                fetch('/get_user_projects_data', {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    const projectList = document.querySelector('.list-group.chat-item');
                    projectList.innerHTML = '';

                    data.user_project_data.forEach(function (project) {
                        const projectItem = document.createElement('li');
                        projectItem.classList.add('list-group-item');
                        projectItem.textContent = project.project_name;
                        projectItem.setAttribute('data-project-id', project._id);
                        projectItem.setAttribute('data-project-name', project.project_name); // store project name

                        projectItem.addEventListener('click', function () {
                            const projectId = projectItem.getAttribute('data-project-id');
                            const projectName = projectItem.getAttribute('data-project-name'); // get project name
                            document.getElementById('chatRoomModal').setAttribute('data-project-id', projectId);
                            document.getElementById('chatRoomModalLabel').innerText = `Chat Room - ${projectName}`; // update modal title

                            fetch('/get_project_messages/' + projectId, {
                                method: 'GET',
                                headers: {
                                    'Content-Type': 'application/json'
                                }
                            })
                            .then(response => response.json())
                            .then(data => {
                                const chatMessages = document.getElementById('chatMessages');
                                chatMessages.innerHTML = '';

                                data.messages.forEach(function (message) {
                                    const messageItem = document.createElement('li');
                                    messageItem.classList.add('list-group-item');
                                    if (message.sender === currentUser) {
                                        messageItem.classList.add('sent');
                                    }
                                    if (message.file_path) {
                                        messageItem.innerHTML = `<strong>${message.sender}: </strong><a href="/${message.file_path}" target="_blank">${message.text}</a>`;
                                    } else {
                                        messageItem.innerHTML = `<strong>${message.sender}: </strong>${message.text}`;
                                    }
                                    chatMessages.appendChild(messageItem);
                                });
                            })
                            .catch(error => {
                                console.error('Error:', error);
                            });

                            $('#chatRoomModal').modal('show');
                        });

                        projectList.appendChild(projectItem);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                });
            } else {
                console.error('Error:', userData.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });

    sendMessageButton.addEventListener("click", function () {
        const messageText = chatInput.value.trim();
        const projectId = document.getElementById('chatRoomModal').getAttribute('data-project-id');

        if (messageText !== "") {
            fetch('/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: messageText,
                    project_id: projectId
                }),
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Gagal mengirim pesan');
                }
                return response.json();
            })
            .then(data => {
                const chatMessages = document.getElementById('chatMessages');
                const messageElement = document.createElement("li");
                messageElement.classList.add("list-group-item", "sent");
                messageElement.innerHTML = `<strong>${currentUser}: </strong>${data.message}`;
                chatMessages.appendChild(messageElement);
                chatInput.value = "";
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
    });

    sendFileButton.addEventListener("click", function () {
        const file = chatFileInput.files[0];
        const projectId = document.getElementById('chatRoomModal').getAttribute('data-project-id');
    
        if (file) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('project_id', projectId);
    
            fetch('/send_chat_file', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Gagal mengunggah file');
                }
                return response.json();
            })
            .then(data => {
                const chatMessages = document.getElementById('chatMessages');
                const messageElement = document.createElement("li");
                messageElement.classList.add("list-group-item", "sent");
                messageElement.innerHTML = `<strong>${currentUser}: </strong><a href="/files/${data.file_path}" target="_blank">${data.message}</a>`;
                chatMessages.appendChild(messageElement);
                chatFileInput.value = "";
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
    });
    
});

